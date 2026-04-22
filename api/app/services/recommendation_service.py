from app.core.clients.gemini import GeminiClient
import os

class RecommendationService:
    def __init__(self, model = "gemini-2.0-flash"):
        self.model = GeminiClient(api_key=os.getenv("GEMINI_API_KEY"), model=model)

    def recommend_pineline(self, query, user_id, top_n=10):
        # Bước 1 xử lý truy vấn để trích xuất thông tin cần thiết
        # Ví dụ: phân tích truy vấn để xác định loại sản phẩm, sở thích của người dùng, v.v.
        processed_query = self._process_query(query)
        # Bước 2: Tạo Seed product từ RAG
        seed_products = self._generate_seed_products(processed_query, user_id)

    def _process_query(self, query):
        try:
            # Bước 1: Convert query sang tiếng anh
            translated_query = self._translate_to_english(query)
        except Exception as e:
            print(f"Error translating query: {e}")
            translated_query = query  # Fallback to original query if translation fails
        return translated_query
    
    def _translate_to_english(self, text):
        prompt = f"Translate the following request to English: {text}"
        return self.model.generate_text(prompt)
    
    def _generate_seed_products(self, processed_query, user_id):
        # Sử dụng RAG để tạo seed products dựa trên processed_query và user_id
        # Ví dụ: Kết hợp thông tin từ cơ sở dữ liệu sản phẩm và lịch sử người dùng để tạo seed products
        pass