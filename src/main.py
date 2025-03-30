import os
from notion_client import Client
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DATABASE_ID = os.getenv("DATABASE_ID")

# 初始化Notion客户端
notion = Client(auth=NOTION_API_KEY)

def get_new_audio_entries():
    """从Notion数据库获取未处理的音频文件"""
    query = notion.databases.query(
        database_id=DATABASE_ID,
        filter={"property": "Status", "select": {"equals": "Pending"}}
    )
    return query.get("results", [])

def transcribe_audio(audio_url):
    """调用DeepSeek API转文本"""
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
    response = requests.post(
        "https://api.deepseek.com/v1/audio/transcriptions",
        headers=headers,
        files={"file": requests.get(audio_url).content},
        data={"model": "whisper-1"}  # 根据DeepSeek文档调整参数
    )
    return response.json()["text"]

def generate_summary(text):
    """生成摘要（示例：使用OpenAI）"""
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": f"请用中文总结以下内容：\n{text}"}]
    )
    return response.choices[0].message.content

def update_notion_page(page_id, text, summary):
    """更新Notion页面"""
    notion.pages.update(
        page_id=page_id,
        properties={
            "Status": {"select": {"name": "Processed"}},
            "Transcript": {"rich_text": [{"text": {"content": text}}]},
            "Summary": {"rich_text": [{"text": {"content": summary}}]}
        }
    )

def main():
    entries = get_new_audio_entries()
    for entry in entries:
        audio_url = entry["properties"]["Audio"]["files"][0]["file"]["url"]
        text = transcribe_audio(audio_url)
        summary = generate_summary(text)  # 或调用其他API
        update_notion_page(entry["id"], text, summary)

if __name__ == "__main__":
    main()
    def get_new_audio_entries():
    """从Notion数据库获取未处理的音频文件"""
    try:
        print("正在查询数据库...")
        query = notion.databases.query(
            database_id=DATABASE_ID,
            filter={"property": "Status", "select": {"equals": "Pending"}}
        )
        entries = query.get("results", [])
        print(f"找到 {len(entries)} 条待处理记录")
        return entries
    except Exception as e:
        print("数据库查询失败:", str(e))
        return []

def transcribe_audio(audio_url):
    """调用DeepSeek API转文本"""
    try:
        print(f"开始转录音频，URL: {audio_url}")
        headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
        response = requests.post(
            "https://api.deepseek.com/v1/audio/transcriptions",
            headers=headers,
            files={"file": requests.get(audio_url).content},
            data={"model": "whisper-1"}
        )
        text = response.json().get("text", "")
        print("转录成功，内容长度:", len(text))
        return text
    except Exception as e:
        print("转录失败:", str(e))
        return ""

def generate_summary(text):
    """生成摘要"""
    try:
        print("正在生成摘要...")
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": f"请用中文总结以下内容：\n{text}"]
        )
        summary = response.choices[0].message.content
        print("摘要生成成功，内容长度:", len(summary))
        return summary
    except Exception as e:
        print("摘要生成失败:", str(e))
        return ""

def update_notion_page(page_id, text, summary):
    """更新Notion页面"""
    try:
        print(f"正在更新页面 {page_id}...")
        notion.pages.update(
            page_id=page_id,
            properties={
                "Status": {"select": {"name": "Processed"}},
                "Transcript": {"rich_text": [{"text": {"content": text}}]},
                "Summary": {"rich_text": [{"text": {"content": summary}}]}
            }
        )
        print("页面更新成功")
    except Exception as e:
        print("页面更新失败:", str(e))
