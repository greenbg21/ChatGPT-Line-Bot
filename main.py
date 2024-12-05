from dotenv import load_dotenv
from flask import Flask, request, abort, jsonify
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, ImageSendMessage, AudioMessage
)
import os
import uuid

from src.models import OpenAIModel
from src.memory import Memory
from src.logger import logger
from src.storage import Storage, FileStorage, MongoStorage
from src.utils import get_role_and_content
from src.service.youtube import Youtube, YoutubeTranscriptReader
from src.service.website import Website, WebsiteReader
from src.mongodb import mongodb

# 塔羅牌資料結構
tarot_data = {
    "MajorArcana": {
        "0": "愚者 心智崩壊、空洞、空虚、資源缺乏、内外一",
        "1": "魔法师 採取行動、醫生",
        "2": "女祭师 運用技巧與知識",
        "3": "皇后 創造性的女性能量、雌激素、女神的力量",
        "4": "皇帝 男性力量、翠固酮、神的力量",
        "5": "教皇 以靈性為中心、放棄自由、獨身守貞",
        "6": "爱人 結合、和諧一致、性、配合、合作",
        "7": "戰車 移動、旅行、行動",
        "8": "力量 力量",
        "9": "隱士 自省、内省、退縮回自我資源(無外援)",
        "10": "命運之輪 改變",
        "11": "正義 和谐、平衡",
        "12": "倒吊人 自我犧牲、服務",
        "13": "死亡 轉化、徹底改觀、完全終結",
        "14": "节制 緩和的、適中的、受保護的",
        "15": "惡魔 不平衡的、被侵襲、受感染、疾病",
        "16": "塔 破壞、崩壞(經常是突然的)",
        "17": "星星 新的開始、神經系統重新開始活動",
        "18": "月亮 幻象、錯覺、隱晦的、未覺察的影響(心識體問題)",
        "19": "太陽 活力",
        "20": "審判 做决定、選擇、依決定行動的能力",
        "21": "世界 完成、實現、滿足、生命"
    },
    "MinorArcana": {
        "Swords": {
            "s1": "防禦、抵抗、呼吸、氣氛、播送、風",
            "s2": "休戰、平衡",
            "s3": "分離、分開、去除、缺口",
            "s4": "疾病、不健康、退縮、戒斷症候、抑鬱、病理性退缩",
            "s5": "交戰、對抗（如：病毒）",
            "s6": "緩慢地進入健康的過程或開始新的活動",
            "s7": "無法察覺的行動或活動（如：感染）",
            "s8": "神經壓迫、無法行動、難以行動",
            "s9": "悲傷、痛苦、不幸、災難、麻煩",
            "s10": "疼痛、受苦"
            "ss1": "劍國王 守護者、警訊，或手術的潛在可能",
            "ss2": "劍皇后 有紀律的、受約束的女性力量",
            "ss3": "劍武士 中樞神經系統受侵擾或發炎",
            "ss4": "劍侍者 神經性的問題，常是局部的"
        },
        "Pentacles": {
            "p1": "阻滯、堵塞、保護、遮蔽、擋開、物質/實質",
            "p2": "（物質上、實質上）平衡",
            "p3": "某些事物運作良好",
            "p4": "執著或抓緊某些物質/實質（如：酒、藥物等）",
            "p5": "沒有足夠的資源/資糧"
            "p6": "配合使用某些必要的物質（常指藥物或正確的飲食）",
            "p7": "保養良好、維護得宜",
            "p8": "身體正致力於某些事物上",
            "p9": "健康、安適、有恰當的資源",
            "p10": "某些事物過度增長、凝結",
            "pp1": "盤國王 祖先、原型、先驅",
            "pp2": "盤皇后 年長的女性力量、更年期",
            "pp3": "盤武士 祖先的模式，意即遺傳性疾病",
            "pp4": "盤侍者 孩童、小幅增长、寄生蟲"
        },
        "Wands": {
            "w1": "內在的火、能量、某些事物正開始發生",
            "w2": "評估、留心、警覺、注意提防",
            "w3": "活動、活躍、活性",
            "w4": "恰當、合適、幸福、幸運",
            "w5": "發炎或感染（常是細菌性的）"
            "w6": "戰勝、克服、獲勝",
            "w7": "勇氣、力量",
            "w8": "許多火的能量或發燒",
            "w9": "從某些事物中存活",
            "w10": "重擔、負擔、煩擾",
            "ww1": "杖國王 侵犯性的（有攻擊性的）男性力量（可能是好的或壞的）",
            "ww2": "杖皇后 創造性的女性力量",
            "ww3": "杖武士 侵犯性/惡性的、猛暴的存在，或侵犯性的疾病",
            "ww4": "杖侍者 皮疹或少量的發炎反應"
        },
        "Cups": {
            "c1": "液體、流暢的、易變的、不固定的、運動的、流動的",
            "c2": "液體/流體/體液的平衡",
            "c3": "健康的（特別指體液相關系統，如心臟、腎臟）",
            "c4": "正在攝取某些事物（如：服用藥物）",
            "c5": "液體/流體/體液的平衡"
            "c6": "受養育/培育的、給予營養物的、或受照護的、在調養的",
            "c7": "無法察覺的影響、找錯方向/場所",
            "c8": "持續地感情用事，情感上甩開過去（終結傷病，迎向未來）",
            "c9": "液體/流體/體液的力量，或情緒穩定",
            "c10": "情緒化的、情緒多變的，或過多的液體（或體液滯留，如：水腫）",
            "cc1": "杯國王 被動/未顯化的男性力量（陰）",
            "cc2": "杯皇后 被動/未顯化的女性力量（陰）",
            "cc3": "杯武士 愛人，或性荷爾蒙",
            "cc4": "杯侍者 處方（常指順勢療法處方）"
        }
    }
}

load_dotenv('.env')

app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
storage = None
youtube = Youtube(step=4)
website = Website()

memory = Memory(system_message=os.getenv('SYSTEM_MESSAGE'), memory_message_count=2)
model_management = {}
api_keys = {}


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)
    return 'OK'


@app.route("/塔羅牌資料", methods=['GET'])
def get_tarot_data():
    return jsonify({"data": tarot_data}), 200


# 以下保留您原來的程式功能
# ...

if __name__ == "__main__":
    if os.getenv('USE_MONGO'):
        mongodb.connect_to_database()
        storage = Storage(MongoStorage(mongodb.db))
    else:
        storage = Storage(FileStorage('db.json'))
    try:
        data = storage.load()
        for user_id in data.keys():
            model_management[user_id] = OpenAIModel(api_key=data[user_id])
    except FileNotFoundError:
        pass
    app.run(host='0.0.0.0', port=8080)
