from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "recommender-ai-service" / "data" / "data_user5000.csv"
OUT_2C = ROOT / "report_assets" / "2c"
OUT_2D = ROOT / "report_assets" / "2d"
FLOW_IMG_PATH = OUT_2C / "rag_flow.png"
CHAT_EXAMPLES_PATH = OUT_2C / "chat_examples.json"
INTEGRATION_JSON_PATH = OUT_2D / "integration_examples.json"
UI_MOCK_PATH = OUT_2D / "ecommerce_chat_ui.png"


@dataclass(frozen=True)
class ProductInfo:
    product_id: str
    title: str
    category: str
    price: int


def category_from_id(product_id: str) -> str:
    numeric = int(product_id.replace("P", ""))
    categories = ["lap-trinh", "kinh-doanh", "tam-ly", "thieu-nhi", "ngoai-ngu"]
    return categories[numeric % len(categories)]


def title_from_category(product_id: str, category: str) -> str:
    prefix = {
        "lap-trinh": "Sách Python Thực Chiến",
        "kinh-doanh": "Sách Quản Trị Hiện Đại",
        "tam-ly": "Sách Tâm Lý Ứng Dụng",
        "thieu-nhi": "Sách Kỹ Năng Cho Trẻ",
        "ngoai-ngu": "Sách Giao Tiếp Tiếng Anh",
    }[category]
    return f"{prefix} ({product_id})"


def build_catalog(df: pd.DataFrame) -> Dict[str, ProductInfo]:
    product_ids = sorted(df["product_id"].astype(str).unique())
    catalog: Dict[str, ProductInfo] = {}
    for pid in product_ids:
        category = category_from_id(pid)
        numeric = int(pid.replace("P", ""))
        price = 79000 + (numeric % 12) * 15000
        catalog[pid] = ProductInfo(
            product_id=pid,
            title=title_from_category(pid, category),
            category=category,
            price=price,
        )
    return catalog


def build_popularity_scores(df: pd.DataFrame) -> pd.Series:
    weights = {
        "view": 1,
        "click": 2,
        "search": 1,
        "add_to_cart": 3,
        "remove_from_cart": -1,
        "add_to_wishlist": 2,
        "remove_from_wishlist": -1,
        "checkout": 4,
        "purchase": 6,
        "rate": 2,
    }
    scored = df.copy()
    scored["score"] = scored["action"].map(weights).fillna(0)
    pop = scored.groupby("product_id", as_index=True)["score"].sum().sort_values(ascending=False)
    return pop


def build_kb_documents() -> List[Dict[str, str]]:
    return [
        {
            "doc_id": "policy_return_01",
            "title": "Chinh sach doi tra",
            "content": "Khach hang duoc doi tra trong 7 ngay neu san pham loi ky thuat hoac giao sai.",
            "tags": ["doi tra", "hoan tien", "chinh sach"],
        },
        {
            "doc_id": "policy_shipping_02",
            "title": "Chinh sach van chuyen",
            "content": "Don hang tren 299000 duoc mien phi van chuyen noi thanh. Don khac tinh phi theo khu vuc.",
            "tags": ["van chuyen", "phi ship", "giao hang"],
        },
        {
            "doc_id": "policy_payment_03",
            "title": "Phuong thuc thanh toan",
            "content": "He thong ho tro COD, chuyen khoan va vi dien tu. Thanh toan online duoc xac nhan tu dong.",
            "tags": ["thanh toan", "cod", "vi dien tu"],
        },
        {
            "doc_id": "recommendation_04",
            "title": "Nguyen tac goi y san pham",
            "content": "Danh sach goi y uu tien hanh vi gan day, do pho bien va muc do lien quan theo do thi tri thuc.",
            "tags": ["goi y", "san pham", "hanh vi"],
        },
    ]


# Marker for report snippet start: def rag_retrieve

def rag_retrieve(query: str, kb_docs: List[Dict[str, str]], top_k: int = 2) -> List[Dict[str, str]]:
    terms = [t.strip().lower() for t in query.replace("?", " ").split() if t.strip()]
    scored = []
    for doc in kb_docs:
        text = f"{doc['title']} {doc['content']} {' '.join(doc['tags'])}".lower()
        score = sum(1 for term in terms if term in text)
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]


# Marker for report snippet end: def rag_retrieve


# Marker for report snippet start: def answer_chat

def answer_chat(query: str, kb_docs: List[Dict[str, str]]) -> Dict[str, object]:
    retrieved = rag_retrieve(query, kb_docs, top_k=2)
    if not retrieved:
        answer = (
            "He thong chua tim thay tri thuc phu hop trong kho du lieu. "
            "Vui long dat cau hoi cu the hon ve chinh sach doi tra, van chuyen hoac thanh toan."
        )
        return {"query": query, "answer": answer, "sources": []}

    source_titles = [doc["title"] for doc in retrieved]
    answer = (
        "Thong tin tu he thong tri thuc: "
        + " | ".join(doc["content"] for doc in retrieved)
        + "\nNguon tham chieu: "
        + ", ".join(source_titles)
    )
    return {"query": query, "answer": answer, "sources": source_titles}


# Marker for report snippet end: def answer_chat


def infer_category_from_query(query: str) -> str:
    q = query.lower()
    if "python" in q or "lap trinh" in q:
        return "lap-trinh"
    if "kinh doanh" in q or "quan tri" in q:
        return "kinh-doanh"
    if "tam ly" in q:
        return "tam-ly"
    if "tre" in q or "thieu nhi" in q:
        return "thieu-nhi"
    return "ngoai-ngu"


# Marker for report snippet start: def build_listing_for_search_or_cart

def build_listing_for_search_or_cart(
    query: str,
    cart_product_ids: List[str],
    catalog: Dict[str, ProductInfo],
    popularity: pd.Series,
    top_k: int = 8,
) -> List[Dict[str, object]]:
    target_category = infer_category_from_query(query)
    ranked_ids = list(popularity.index)

    suggestions = []
    for pid in ranked_ids:
        if pid in cart_product_ids or pid not in catalog:
            continue
        info = catalog[pid]
        category_bonus = 2 if info.category == target_category else 0
        score = float(popularity.get(pid, 0)) + category_bonus
        suggestions.append(
            {
                "product_id": info.product_id,
                "title": info.title,
                "category": info.category,
                "price": info.price,
                "score": round(score, 2),
            }
        )

    suggestions.sort(key=lambda x: x["score"], reverse=True)
    return suggestions[:top_k]


# Marker for report snippet end: def build_listing_for_search_or_cart


def draw_box(draw: ImageDraw.ImageDraw, xy, text: str, fill: str, border: str = "#1f2937", font=None) -> None:
    draw.rounded_rectangle(xy, radius=16, fill=fill, outline=border, width=2)
    x1, y1, x2, y2 = xy
    w, h = draw.textbbox((0, 0), text, font=font)[2:]
    draw.text(((x1 + x2 - w) / 2, (y1 + y2 - h) / 2), text, fill="#111827", font=font)


def draw_arrow(draw: ImageDraw.ImageDraw, p1, p2, color="#334155", width=3):
    draw.line([p1, p2], fill=color, width=width)
    ax, ay = p2
    draw.polygon([(ax, ay), (ax - 10, ay - 5), (ax - 10, ay + 5)], fill=color)


def create_rag_flow_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1800, 900), "#fffaf5")
    draw = ImageDraw.Draw(img)

    font_title = ImageFont.truetype("C:/Windows/Fonts/timesbd.ttf", 42)
    font_box = ImageFont.truetype("C:/Windows/Fonts/times.ttf", 28)
    font_note = ImageFont.truetype("C:/Windows/Fonts/times.ttf", 24)

    draw.text((60, 30), "Luồng RAG dựa trên KB_Graph trong hệ thống e-commerce", fill="#7f1d1d", font=font_title)

    draw_box(draw, (90, 180, 350, 300), "Người dùng đặt câu hỏi", "#fee2e2", font=font_box)
    draw_box(draw, (430, 180, 690, 300), "Phân loại ý định", "#ffedd5", font=font_box)
    draw_box(draw, (770, 120, 1080, 240), "Truy vấn KB_Graph\n(Neo4j)", "#dbeafe", font=font_box)
    draw_box(draw, (770, 280, 1080, 400), "Vector Retrieval\n(KB văn bản)", "#dcfce7", font=font_box)
    draw_box(draw, (1160, 180, 1450, 300), "Hợp nhất ngữ cảnh", "#fef3c7", font=font_box)
    draw_box(draw, (1520, 180, 1730, 300), "Sinh phản hồi chat", "#ede9fe", font=font_box)

    draw_arrow(draw, (350, 240), (430, 240))
    draw_arrow(draw, (690, 240), (770, 180))
    draw_arrow(draw, (690, 240), (770, 340))
    draw_arrow(draw, (1080, 180), (1160, 220))
    draw_arrow(draw, (1080, 340), (1160, 260))
    draw_arrow(draw, (1450, 240), (1520, 240))

    draw.text((90, 500), "Nguyên tắc: chỉ trả lời dựa trên nguồn truy hồi; ưu tiên minh bạch nguồn và khả năng kiểm chứng.", fill="#374151", font=font_note)
    draw.text((90, 540), "Ứng dụng: tư vấn chính sách, giải thích đề xuất, hỗ trợ truy vấn sản phẩm theo ngữ cảnh người dùng.", fill="#374151", font=font_note)

    img.save(path)


def create_ui_mock(path: Path, listings: List[Dict[str, object]], chat_answers: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1800, 980), "#fff7f7")
    draw = ImageDraw.Draw(img)

    font_title = ImageFont.truetype("C:/Windows/Fonts/timesbd.ttf", 34)
    font_text = ImageFont.truetype("C:/Windows/Fonts/times.ttf", 24)
    font_small = ImageFont.truetype("C:/Windows/Fonts/times.ttf", 20)

    draw.rounded_rectangle((40, 30, 1760, 930), radius=16, fill="#ffffff", outline="#fecaca", width=3)
    draw.text((70, 55), "Mô phỏng tích hợp e-commerce: danh sách hàng + chat tư vấn", fill="#991b1b", font=font_title)

    # Left: listing
    draw.rounded_rectangle((70, 120, 980, 880), radius=12, fill="#fff1f2", outline="#fca5a5", width=2)
    draw.text((90, 145), "Danh sách gợi ý khi khách hàng search/chọn giỏ hàng", fill="#7f1d1d", font=font_text)

    y = 190
    for i, item in enumerate(listings[:8], start=1):
        line = f"{i:02d}. {item['title']} | {item['category']} | {item['price']:,} đ | score={item['score']}"
        draw.text((95, y), line, fill="#111827", font=font_small)
        y += 42

    # Right: chat panel
    draw.rounded_rectangle((1020, 120, 1730, 880), radius=12, fill="#fff7ed", outline="#fdba74", width=2)
    draw.text((1040, 145), "Giao diện chat tư vấn cho người dùng", fill="#9a3412", font=font_text)

    y_chat = 195
    for item in chat_answers[:2]:
        q = f"User: {item['query']}"
        a = f"Bot: {item['answer'][:120]}..."
        s = f"Nguồn: {', '.join(item['sources']) if item['sources'] else 'Không có'}"
        draw.text((1040, y_chat), q, fill="#7c2d12", font=font_small)
        y_chat += 34
        draw.text((1040, y_chat), a, fill="#1f2937", font=font_small)
        y_chat += 34
        draw.text((1040, y_chat), s, fill="#065f46", font=font_small)
        y_chat += 56

    draw.text((1040, 790), "Thiết kế giao diện tùy biến trong hệ thống, không sử dụng giao diện mặc định của ChatGPT.", fill="#1f2937", font=font_small)

    img.save(path)


def main() -> int:
    if not DATA_PATH.exists():
        return 1

    OUT_2C.mkdir(parents=True, exist_ok=True)
    OUT_2D.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATA_PATH)
    catalog = build_catalog(df)
    popularity = build_popularity_scores(df)
    kb_docs = build_kb_documents()

    chat_queries = [
        "Chính sách đổi trả của cửa hàng như thế nào?",
        "Tôi muốn biết phí vận chuyển khi mua online",
        "Hệ thống gợi ý sản phẩm dựa trên yếu tố nào?",
    ]
    chat_answers = [answer_chat(q, kb_docs) for q in chat_queries]

    listing_search = build_listing_for_search_or_cart(
        query="sách python cho người mới", cart_product_ids=["P0135", "P0055"], catalog=catalog, popularity=popularity, top_k=8
    )

    integration_examples = {
        "search_query": "sách python cho người mới",
        "cart_product_ids": ["P0135", "P0055"],
        "listing_results": listing_search,
        "chat_examples": chat_answers,
    }

    create_rag_flow_image(FLOW_IMG_PATH)
    create_ui_mock(UI_MOCK_PATH, listing_search, chat_answers)

    CHAT_EXAMPLES_PATH.write_text(json.dumps(chat_answers, ensure_ascii=False, indent=2), encoding="utf-8")
    INTEGRATION_JSON_PATH.write_text(json.dumps(integration_examples, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
