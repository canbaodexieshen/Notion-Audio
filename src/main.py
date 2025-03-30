import os
from notion_client import Client
import requests
from dotenv import load_dotenv
import logging

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DATABASE_ID = os.getenv("DATABASE_ID")

# 初始化Notion客户端
notion = Client(auth=NOTION_API_KEY)

# ---------------------- 核心函数（含详细日志） ----------------------
def get_new_audio_entries():
    """从数据库获取待处理的音频条目"""
    try:
        logger.info("正在查询数据库...")
        query = notion.databases.query(
            database_id=DATABASE_ID,
            filter={
                "property": "Status",
                "select": {"equals": "Pending"}
            }
        )
        entries = query.get("results", [])
        logger.info(f"找到 {len(entries)} 条待处理记录")
        return entries
    except Exception as e:
        logger.error(f"数据库查询失败: {str(e)}")
        return []

def transcribe_audio(audio_url):
    """调用DeepSeek API转文本"""
    try:
        logger.info(f"开始转录音频，URL: {audio_url}")
        
        # 下载音频文件
        response = requests.get(audio_url)
        if response.status_code != 200:
            logger.error(f"音频下载失败，HTTP状态码: {response.status_code}")
            return ""
        
        # 调用DeepSeek API
        headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
        api_response = requests.post(
            "https://api.deepseek.com/v1/audio/transcriptions",
            headers=headers,
            files={"file": response.content},
            data={"model": "whisper-1"}
        )
        
        # 检查API响应
        if api_response.status_code != 200:
            logger.error(f"DeepSeek API调用失败，状态码: {api_response.status_code}")
            logger.error(f"响应内容: {api_response.text}")
            return ""
        
        text = api_response.json().get("text", "")
        logger.info(f"转录成功，内容长度: {len(text)} 字符")
        return text
    except Exception as e:
        logger.error(f"转录过程中发生异常: {str(e)}")
        return ""

def generate_summary(text):
    """生成摘要"""
    try:
        if not text:
            logger.warning("输入文本为空，跳过摘要生成")
            return ""
            
        logger.info("正在生成摘要...")
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role": "user",
                "content": f"请用中文总结以下内容，保留关键信息：\n{text}"
            }]
        )
        
        summary = response.choices[0].message.content
        logger.info(f"摘要生成成功，内容长度: {len(summary)} 字符")
        return summary
    except Exception as e:
        logger.error(f"摘要生成失败: {str(e)}")
        return ""

def update_notion_page(page_id, text, summary):
    """更新Notion页面"""
    try:
        logger.info(f"准备更新页面 {page_id}...")
        
        # 构建属性对象
        properties = {
            "Status": {"select": {"name": "Processed"}},
            "Transcript": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": text}
                }]
            },
            "Summary": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": summary}
                }]
            }
        }
        
        # 调试输出属性结构
        logger.debug("更新属性结构: %s", properties)
        
        # 执行更新
        notion.pages.update(
            page_id=page_id,
            properties=properties
        )
        logger.info("页面更新成功")
    except Exception as e:
        logger.error(f"页面更新失败: {str(e)}")

# ---------------------- 主流程 ----------------------
def main():
    try:
        logger.info("========== 开始处理流程 ==========")
        
        # 步骤1：获取待处理条目
        entries = get_new_audio_entries()
        if not entries:
            logger.warning("没有需要处理的条目")
            return
            
        # 步骤2：处理每个条目
        for idx, entry in enumerate(entries):
            logger.info(f"处理第 {idx+1}/{len(entries)} 个条目")
            
            # 获取音频URL
            try:
                audio_data = entry["properties"]["Audio"]["files"][0]
                audio_url = audio_data["file"]["url"]
                logger.info(f"解析到音频URL: {audio_url}")
            except (KeyError, IndexError) as e:
                logger.error("音频URL解析失败，请检查数据库字段结构")
                logger.error(f"原始数据: {entry['properties']['Audio']}")
                continue
                
            # 转录音频
            text = transcribe_audio(audio_url)
            if not text:
                logger.error("转录失败，跳过后续处理")
                continue
                
            # 生成摘要
            summary = generate_summary(text)
            
            # 更新页面
            update_notion_page(entry["id"], text, summary)
            
        logger.info("========== 处理完成 ==========")
    except Exception as e:
        logger.error(f"主流程发生未捕获的异常: {str(e)}")

if __name__ == "__main__":
    main()
