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
