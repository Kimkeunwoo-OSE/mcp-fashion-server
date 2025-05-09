import torch
from PIL import Image
import os
import logging
import json
from transformers import CLIPProcessor, CLIPModel

# 로깅 설정
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 디바이스 설정
device = "cuda" if torch.cuda.is_available() else "cpu"

# 모델 및 프로세서 로딩 (Fashion-CLIP)
try:
    model = CLIPModel.from_pretrained("patrickjohncyh/fashion-clip")
    processor = CLIPProcessor.from_pretrained("patrickjohncyh/fashion-clip")
    model = model.to(device)
    logger.info(f"Fashion-CLIP 모델 로드 완료 (장치: {device})")
except Exception as e:
    logger.error(f"Fashion-CLIP 모델 로드 실패: {str(e)}")
    raise

# 프롬프트 로드
PROMPT_FILE = r"C:\Users\kku72\Desktop\MCP_Server\config\prompts.json"
with open(PROMPT_FILE, "r", encoding="utf-8") as f:
    prompts_data = json.load(f)
CLOTHING_PROMPTS = prompts_data["categories"]

CATEGORY_LIST = list(prompts_data["categories"].keys())

def classify_clothing(image_path: str):
    image = Image.open(image_path).convert('RGB')
    
    # 1) 분류 후보를 리스트로 넘김
    inputs = processor(
        text=CATEGORY_LIST,     # dict 대신 str 리스트
        images=image,
        return_tensors="pt",
        padding=True
    ).to(device)
    
    outputs = model(**inputs)
    probs = outputs.logits_per_image.softmax(dim=1)
    best_idx = probs.argmax().item()
    
    # 2) 인덱스에 맞추어 분류 결과 얻기
    best_prompt = CATEGORY_LIST[best_idx]
    confidence = probs[0, best_idx].item()
    
    # 3) 저신뢰도 처리
    if confidence < 0.2:
        best_prompt = "검토 필요"
    
    logger.info(f"분류 결과: {best_prompt} (신뢰도: {confidence:.4f})")
    return best_prompt, get_style_description(best_prompt), confidence

def get_style_description(category: str) -> str:
    return f"{category} 스타일의 옷입니다."

def analyze_clothing_image(image_path: str):
    """이미지 종합 분석"""
    try:
        category, confidence = classify_clothing(image_path)

        result = {
            "category": category,
            "confidence": confidence
        }
        return result

    except Exception as e:
        logger.error(f"종합 분석 실패: {str(e)}")
        return {}

# 테스트 코드
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        img_path = sys.argv[1]
        if os.path.exists(img_path):
            result = analyze_clothing_image(img_path)
            print(result)
        else:
            print(f"❌ 파일을 찾을 수 없습니다: {img_path}")
    else:
        print("사용법: python clip_classifier.py [이미지 파일 경로]")
