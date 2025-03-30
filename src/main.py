import os
import requests
import logging
from notion_client import Client
from dotenv import load_dotenv
from openai import OpenAI  # 如果使用OpenAI摘要

# ---------------------- 配置 ----------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("NotionAudioProcessor")

load_dotenv()

# 环境变量校验
REQUIRED_ENV = ["NOTION_API_KEY", "DEEPSEEK_API_KEY", "DATABASE_ID"]
missing_env = [var for var in REQUIRED_ENV if not os.getenv(var)]
if missing_env:
    logger.critical(f"缺少必需的环境变量: {missing_env}")
    exit(1)

# 初始化客户端
notion = Client(auth=os.getenv("NOTION_API_KEY"), log_level=logging.WARNING)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None

# ---------------------- 核心函数 ----------------------
def validate_database_schema():
    """验证数据库字段结构是否匹配"""
    try:
        logger.info("校验数据库结构...")
        db = notion.databases.retrieve(database_id=os.getenv("DATABASE_ID"))
        props = db["properties"]
        
        required_fields = {
            "Status": {"type": "select", "options": ["Pending", "Processed"]},
            "Audio": {"type": "files"},
            "Transcript": {"type": "rich_text"},
            "Summary": {"type": "rich_text"}
        }
        
        for field, config in required_fields.items():
            if field not in props:
                raise ValueError(f"缺少必需字段: {field}")
            if props[field]["type"] != config["type"]:
                raise ValueError(f"字段 '{field}' 类型应为 {config['type']}, 实际是 {props[field]['type']}")
            if config.get("options") and not any(opt["name"] in config["options"] for opt in props[field]["select"]["options"]):
                raise ValueError(f"字段 '{field}' 缺少必需选项: {config['options']}")
        
        logger.info("数据库结构校验通过")
        return True
    except Exception as e:
        logger.critical(f"数据库结构不兼容: {str(e)}")
        return False

def get_pending_entries():
    """获取待处理的Notion条目"""
    try:
        logger.info("查询待处理条目...")
        response = notion.databases.query(
            database_id=os.getenv("DATABASE_ID"),
            filter={
                "property": "Status",
                "select": {"equals": "Pending"}
            }
        )
        entries = response.get("results", [])
        logger.info(f"找到 {len(entries)} 个待处理条目")
        return entries
    except Exception as e:
        logger.error(f"查询数据库失败: {str(e)}")
        return []

def download_audio(audio_url):
    """下载音频文件并验证"""
    try:
        logger.info(f"下载音频文件: {audio_url}")
        response = requests.get(audio_url, timeout=10)
        response.raise_for_status()
        
        if len(response.content) == 0:
            logger.error("音频文件内容为空")
            return None
            
        return response.content
    except Exception as e:
        logger.error(f"音频下载失败: {str(e)}")
        return None

def transcribe_with_deepseek(audio_data):
    """调用DeepSeek API进行转录"""
    try:
        logger.info("调用DeepSeek API进行转录...")
        headers = {
            "Authorization": f"Bearer {os.getenv('DEEPSEEK_API_KEY')}",
            "Content-Type": "multipart/form-data"
        }
        response = requests.post(
            "https://api.deepseek.com/v1/audio/transcriptions",
            headers=headers,
            files={"file": ("audio.mp3", audio_data)},
            data={"model": "whisper-1"},
            timeout=30
        )
        response.raise_for_status()
        
        transcript = response.json().get("text", "")
        logger.info(f"转录成功，字符数: {len(transcript)}")
        return transcript
    except Exception as e:
        logger.error(f"转录失败: {str(e)}")
        if response:
            logger.debug(f"API响应: {response.text}")
        return ""

def generate_summary(text):
    """生成摘要（使用OpenAI）"""
    if not text or not openai_client:
        return ""
        
    try:
        logger.info("生成内容摘要...")
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role": "user",
                "content": f"用简洁的中文总结以下内容，保留关键信息：\n{text}"
            }],
            temperature=0.5,
            max_tokens=300
        )
        summary = response.choices[0].message.content
        logger.info(f"摘要生成成功，字符数: {len(summary)}")
        return summary
    except Exception as e:
        logger.error(f"摘要生成失败: {str(e)}")
        return ""

def update_notion_page(page_id, transcript, summary):
    """更新Notion页面"""
    try:
        logger.info(f"更新页面 {page_id}...")
        
        # 构建符合Notion API要求的属性结构
        properties = {
            "Status": {"select": {"name": "Processed"}},
            "Transcript": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": transcript},
                    "annotations": {"bold": False, "italic": False, "code": False},
                    "plain_text": transcript
                }]
            },
            "Summary": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": summary},
                    "annotations": {"bold": False, "italic": False, "code": False},
                    "plain_text": summary
                }]
            }
        }
        
        # 调试输出
        logger.debug("更新属性: %s", properties)
        
        response = notion.pages.update(
            page_id=page_id,
            properties=properties
        )
        
        # 验证更新结果
        if response["properties"]["Status"]["select"]["name"] != "Processed":
            raise ValueError("状态更新失败")
            
        logger.info("页面更新成功")
        return True
    except Exception as e:
        logger.error(f"更新失败: {str(e)}")
        logger.debug("错误详情: %s", response if 'response' in locals() else "")
        return False

# ---------------------- 主流程 ----------------------
def main():
    logger.info("======== 开始处理流程 ========")
    
    # 前置校验
    if not validate_database_schema():
        logger.error("数据库结构校验失败，终止运行")
        return
    
    entries = get_pending_entries()
    if not entries:
        logger.info("没有需要处理的条目")
        return
    
    for entry in entries:
        logger.info(f"处理条目: {entry['id']}")
        
        # 获取音频文件
        try:
            file_prop = entry["properties"]["Audio"]["files"][0]
            audio_url = file_prop["file"]["url"]
        except (KeyError, IndexError) as e:
            logger.error(f"音频URL解析失败: {str(e)}")
            logger.debug("原始Audio属性: %s", entry["properties"]["Audio"])
            continue
            
        # 下载音频
        audio_data = download_audio(audio_url)
        if not audio_data:
            continue
            
        # 转录音频
        transcript = transcribe_with_deepseek(audio_data)
        if not transcript:
            logger.error("跳过无转录结果的条目")
            continue
            
        # 生成摘要
        summary = generate_summary(transcript)
        
        # 更新Notion
        success = update_notion_page(entry["id"], transcript, summary)
        if not success:
            logger.error("条目处理失败，保留Pending状态")
            
    logger.info("======== 处理完成 ========")

if __name__ == "__main__":
    main()
