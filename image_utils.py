import os
import cv2
import numpy as np
from PIL import Image
import logging
from clip_classifier import classify_clothing
import pathlib
from typing import Tuple, List, Dict, Any, Optional
import configparser
import torch
import json
from datetime import datetime
import shutil
from PIL.ExifTags import TAGS


# 로깅 설정
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 설정 파일 경로 및 기본 설정
BASE_DIR = pathlib.Path(__file__).parent.absolute()
CONFIG_FILE = os.path.join(BASE_DIR, "config", "image_utils.ini")

# 기본 설정값
DEFAULT_CONFIG = {
    "ImageClassification": {
        "wear_threshold": "0.15",  # 착용컷 판단 임계값
        "min_face_size": "30",     # 얼굴 감지 최소 크기
        "scale_factor": "1.05",    # HOG 스케일 팩터
        "win_stride": "4,4",       # HOG 윈도우 스트라이드
        "padding": "8,8",          # HOG 패딩
        "use_face_detection": "True", # 얼굴 감지 사용 여부
        "face_weight": "15.0",     # 얼굴 면적 가중치
        "max_dimension": "1000",   # 최대 이미지 크기
        "hog_hit_threshold": "0.0", # HOG 감지 임계값
        "face_min_neighbors": "5"  # 얼굴 감지 최소 이웃 수
    },
    "StyleAnalysis": {
        "use_clip_model": "True",   # CLIP 모델 사용 여부
        "confidence_threshold": "0.6" # 스타일 분석 신뢰도 임계값
    }
}

# 설정 로드 함수
def load_config():
    """설정 파일 로드 또는 생성"""
    config = configparser.ConfigParser()
    
    # 기본 설정 추가
    for section, options in DEFAULT_CONFIG.items():
        if not config.has_section(section):
            config.add_section(section)
        for option, value in options.items():
            config.set(section, option, value)
    
    # 설정 파일이 있으면 로드
    if os.path.exists(CONFIG_FILE):
        try:
            config.read(CONFIG_FILE)
            logger.info(f"설정 파일 로드: {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"설정 파일 로드 중 오류: {str(e)}")
    else:
        # 설정 파일이 없으면 생성
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, 'w') as f:
                config.write(f)
            logger.info(f"기본 설정 파일 생성: {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"설정 파일 생성 중 오류: {str(e)}")
    
    return config

# 전역 설정 로드
config = load_config()
WEAR_THRESHOLD = config.getfloat("ImageClassification", "wear_threshold", fallback=0.15)
USE_FACE_DETECTION = config.getboolean("ImageClassification", "use_face_detection", fallback=True)

# 얼굴 감지기 초기화
try:
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    if face_cascade.empty():
        logger.error("얼굴 감지기 로드 실패, 기본 HOG 사람 감지기만 사용")
        USE_FACE_DETECTION = False
except Exception as e:
    logger.error(f"얼굴 감지기 초기화 중 오류: {str(e)}")
    USE_FACE_DETECTION = False

def detect_human_ratio(image_path: str) -> float:
    """
    사람 비율을 계산하여, 착용컷/디테일컷을 구분
    향상된 감지 알고리즘:
    1. HOG 기반 사람 검출 (전신 감지)
    2. Haar Cascade 얼굴 검출 (얼굴 감지)
    """
    try:
        if not os.path.exists(image_path):
            logger.error(f"이미지 파일이 없습니다: {image_path}")
            return 0
        
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"이미지를 읽을 수 없습니다: {image_path}")
            return 0
        
        # 이미지 크기 확인 및 조정 (너무 큰 이미지는 처리 시간이 오래 걸림)
        height, width = image.shape[:2]
        max_dimension = 1000  # 최대 크기 제한
        if max(height, width) > max_dimension:
            scale = max_dimension / max(height, width)
            image = cv2.resize(image, (int(width * scale), int(height * scale)))
            height, width = image.shape[:2]
        
        person_area = 0
        total_area = height * width
        
        # 1. HOG 기반 사람 검출
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            hog = cv2.HOGDescriptor()
            hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            
            win_stride = tuple(map(int, config.get("ImageClassification", "win_stride", fallback="4,4").split(',')))
            padding = tuple(map(int, config.get("ImageClassification", "padding", fallback="8,8").split(',')))
            scale_factor = config.getfloat("ImageClassification", "scale_factor", fallback=1.05)
            
            (regions, _) = hog.detectMultiScale(gray, 
                                              winStride=win_stride,
                                              padding=padding, 
                                              scale=scale_factor)
            
            for (x, y, w, h) in regions:
                person_area += w * h
        except Exception as e:
            logger.warning(f"HOG 감지 중 오류: {str(e)}")
        
        # 2. 얼굴 감지 (여성 의류 착용컷의 경우 얼굴이 포함될 가능성 높음)
        if USE_FACE_DETECTION:
            try:
                min_face_size = config.getint("ImageClassification", "min_face_size", fallback=30)
                faces = face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=config.getint("ImageClassification", "face_min_neighbors", fallback=5),
                    minSize=(min_face_size, min_face_size),
                    flags=cv2.CASCADE_SCALE_IMAGE
)
                
                # 얼굴이 감지되면 가중치 적용 (착용컷일 가능성 높음)
                if len(faces) > 0:
                    # 얼굴 면적의 약 15배를 사람 면적으로 추정 (경험적 값)
                    face_area = sum([w * h for (x, y, w, h) in faces])
                    estimated_person_area = face_area * 15
                    person_area = max(person_area, estimated_person_area)
            except Exception as e:
                logger.warning(f"얼굴 감지 중 오류: {str(e)}")
        
        # 사람 비율 계산 (0~1 사이 값)
        ratio = person_area / total_area if total_area else 0
        logger.debug(f"이미지 {os.path.basename(image_path)}: 사람 비율 = {ratio:.4f}")
        
        return ratio
        
    except Exception as e:
        logger.error(f"사람 감지 중 오류 발생: {str(e)}")
        return 0

def classify_image(image_path: str, threshold: Optional[float] = None) -> str:
    """
    이미지에서 사람의 비율을 기반으로 착용컷/디테일컷을 구분하는 함수
    """
    if threshold is None:
        threshold = WEAR_THRESHOLD
        
    try:
        ratio = detect_human_ratio(image_path)
        image_type = "wear" if ratio >= threshold else "detail"
        logger.info(f"이미지 분류 결과: {os.path.basename(image_path)} -> {image_type} (비율: {ratio:.4f})")
        return image_type
    except Exception as e:
        logger.error(f"이미지 분류 중 오류: {str(e)}")
        # 오류 발생 시 기본값으로 detail 반환
        return "detail"

def classify_images(image_paths: List[str]) -> Tuple[List[str], List[str]]:
    """
    주어진 이미지 경로들을 분류하고 착용컷과 디테일컷으로 구분
    Returns: (착용컷 리스트, 디테일컷 리스트)
    """
    wear_images = []
    detail_images = []
    
    total = len(image_paths)
    logger.info(f"총 {total}개 이미지 분류 시작")
    
    for i, image_path in enumerate(image_paths):
        try:
            if i % 10 == 0:
                logger.info(f"진행 중... {i}/{total}")
                
            image_type = classify_image(image_path)
            
            # 이미지 확장자 확인
            _, ext = os.path.splitext(image_path)
            if ext.lower() not in ['.jpg', '.jpeg', '.png', '.gif']:
                logger.warning(f"지원되지 않는 이미지 형식: {image_path}")
                continue
                
            basename = os.path.basename(image_path)
            
            if image_type == "wear":
                wear_images.append(basename)
            else:
                detail_images.append(basename)
                
        except Exception as e:
            logger.error(f"이미지 처리 중 오류: {str(e)}")
            continue
    
    logger.info(f"이미지 분류 완료: 착용컷 {len(wear_images)}개, 디테일컷 {len(detail_images)}개")
    return wear_images, detail_images

def validate_image(image_path: str) -> bool:
    """이미지 파일 유효성 검사"""
    try:
        img = Image.open(image_path)
        img.verify()  # 이미지 유효성 확인
        return True
    except Exception as e:
        logger.warning(f"유효하지 않은 이미지: {image_path} - {str(e)}")
        return False

def process_clothing_images(image_folder: str) -> Dict[str, Any]:
    """
    폴더 내 모든 의류 이미지를 처리하여 착용컷/디테일컷 분류 및 카테고리 분석
    Returns: {
        'wear': 착용컷 이미지 리스트,
        'detail': 디테일컷 이미지 리스트,
        'categories': {이미지명: 카테고리}, 
        'descriptions': {이미지명: 설명}
    }
    """
    result = {
        'wear': [],
        'detail': [],
        'categories': {},
        'descriptions': {}
    }
    
    try:
        image_paths = []
        for root, _, files in os.walk(image_folder):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    image_paths.append(os.path.join(root, file))
        
        logger.info(f"{len(image_paths)}개 이미지 발견")
        
        # 이미지 유효성 검사
        valid_images = [img for img in image_paths if validate_image(img)]
        logger.info(f"{len(valid_images)}개 유효한 이미지")
        
        # 착용컷/디테일컷 분류
        wear, detail = classify_images(valid_images)
        result['wear'] = wear
        result['detail'] = detail
        
        # 의류 카테고리 및 스타일 분석
        for img_path in valid_images:
            basename = os.path.basename(img_path)
            try:
                category, description, _ = classify_clothing(img_path)
                result['categories'][basename] = category
                result['descriptions'][basename] = description
            except Exception as e:
                logger.error(f"의류 분류 중 오류: {str(e)}")
                result['categories'][basename] = "unknown"
                result['descriptions'][basename] = "분류할 수 없는 이미지입니다."
        
        return result
    
    except Exception as e:
        logger.error(f"이미지 처리 중 오류 발생: {str(e)}")
        return result

# 테스트용 코드
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        if os.path.exists(image_path):
            if os.path.isdir(image_path):
                # 폴더 처리
                results = process_clothing_images(image_path)
                print(f"착용컷: {len(results['wear'])}개")
                print(f"디테일컷: {len(results['detail'])}개")
                print(f"분류된 카테고리: {len(results['categories'])}개")
            else:
                # 단일 이미지 처리
                image_type = classify_image(image_path)
                ratio = detect_human_ratio(image_path)
                category, description, score = classify_clothing(image_path)
                
                print(f"이미지 유형: {image_type} (사람 비율: {ratio:.4f})")
                print(f"의류 카테고리: {category} (유사도 점수: {score})")
                print(f"스타일 설명: {description}")
        else:
            print(f"파일 또는 디렉토리가 존재하지 않습니다: {image_path}")
    else:
        print("사용법: python image_utils.py [이미지 경로 또는 디렉토리]")
        
        
def resize_for_processing(image: np.ndarray, max_dimension: int = 1000) -> np.ndarray:
    """
    이미지 처리를 위한 크기 조정 함수
    너무 큰 이미지는 처리 시간이 오래 걸리므로 적절한 크기로 조정
    """
    height, width = image.shape[:2]
    
    if max(height, width) <= max_dimension:
        return image
        
    scale = max_dimension / max(height, width)
    return cv2.resize(image, (int(width * scale), int(height * scale)))

def detect_human_with_hog(image: np.ndarray, config: configparser.ConfigParser) -> float:
    """HOG 기반 사람 감지 함수"""
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        
        win_stride = tuple(map(int, config.get("ImageClassification", "win_stride", fallback="4,4").split(',')))
        padding = tuple(map(int, config.get("ImageClassification", "padding", fallback="8,8").split(',')))
        scale_factor = config.getfloat("ImageClassification", "scale_factor", fallback=1.05)
        hit_threshold = config.getfloat("ImageClassification", "hog_hit_threshold", fallback=0.0)
        
        (regions, _) = hog.detectMultiScale(
            gray,
            winStride=win_stride,
            padding=padding,
            scale=scale_factor,
            hitThreshold=hit_threshold
        )
        
        # 감지된 사람 영역 면적 계산
        person_area = sum(w * h for (x, y, w, h) in regions)
        return person_area
    except Exception as e:
        logger.warning(f"HOG 사람 감지 중 오류: {str(e)}")
        return 0

def detect_faces(image: np.ndarray, config: configparser.ConfigParser) -> Tuple[int, List[Tuple[int, int, int, int]]]:
    """얼굴 감지 함수"""
    try:
        if not USE_FACE_DETECTION:
            return 0, []
            
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        min_face_size = config.getint("ImageClassification", "min_face_size", fallback=30)
        min_neighbors = config.getint("ImageClassification", "face_min_neighbors", fallback=5)
        
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=min_neighbors,
            minSize=(min_face_size, min_face_size),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        # 감지된 얼굴 영역 면적 계산
        face_area = sum(w * h for (x, y, w, h) in faces)
        return face_area, faces
    except Exception as e:
        logger.warning(f"얼굴 감지 중 오류: {str(e)}")
        return 0, []

def get_image_metadata(image_path: str) -> Dict[str, Any]:
    """이미지 메타데이터 추출 함수"""
    try:
        with Image.open(image_path) as img:
            metadata = {
                "format": img.format,
                "mode": img.mode,
                "size": img.size,
                "width": img.width,
                "height": img.height
            }
            
            # EXIF 데이터 추출 시도
            if hasattr(img, '_getexif') and img._getexif():
                exif = img._getexif()
                if exif:
                    metadata["exif"] = {}
                    for tag_id, value in exif.items():
                        tag_name = TAGS.get(tag_id, tag_id)
                        metadata["exif"][tag_name] = value
            
            return metadata
    except Exception as e:
        logger.warning(f"이미지 메타데이터 추출 중 오류: {str(e)}")
        return {"error": str(e)}

def extract_dominant_colors(image_path: str, num_colors: int = 5) -> List[Tuple[int, int, int]]:
    """이미지에서 주요 색상 추출 함수"""
    try:
        image = cv2.imread(image_path)
        if image is None:
            return []
            
        # 이미지 크기 조정 (처리 속도 향상)
        image = resize_for_processing(image, 300)
        
        # 이미지를 1차원 배열로 변환
        pixels = image.reshape((-1, 3))
        pixels = np.float32(pixels)
        
        # K-means 클러스터링으로 주요 색상 추출
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 0.2)
        _, labels, centers = cv2.kmeans(pixels, num_colors, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
        
        # 각 클러스터의 크기 계산
        counts = np.bincount(labels.flatten())
        
        # 색상을 RGB로 변환하고 빈도에 따라 정렬
        colors = []
        for i in range(num_colors):
            color = centers[i].astype(np.uint8)
            # BGR -> RGB 변환
            colors.append(((int(color[2]), int(color[1]), int(color[0])), counts[i]))
            
        # 빈도 기준으로 정렬
        colors.sort(key=lambda x: x[1], reverse=True)
        
        # 색상만 반환
        return [color for color, _ in colors]
    except Exception as e:
        logger.warning(f"주요 색상 추출 중 오류: {str(e)}")
        return []

def batch_process_images(image_folder: str, output_folder: str, generate_report: bool = True) -> Dict[str, Any]:
    """여러 이미지를 일괄 처리하고 보고서 생성"""
    start_time = datetime.now()
    
    result = {
        'wear': [],
        'detail': [],
        'categories': {},
        'descriptions': {},
        'colors': {},
        'metadata': {},
        'start_time': start_time,
        'end_time': None,
        'total_images': 0,
        'processed_images': 0,
        'failed_images': 0
    }
    
    try:
        # 출력 폴더 생성
        os.makedirs(output_folder, exist_ok=True)
        wear_folder = os.path.join(output_folder, "wear")
        detail_folder = os.path.join(output_folder, "detail")
        os.makedirs(wear_folder, exist_ok=True)
        os.makedirs(detail_folder, exist_ok=True)
        
        # 이미지 목록 수집
        image_paths = []
        for root, _, files in os.walk(image_folder):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    image_paths.append(os.path.join(root, file))
        
        result['total_images'] = len(image_paths)
        logger.info(f"총 {result['total_images']}개 이미지 처리 시작")
        
        # 각 이미지 처리
        for img_path in image_paths:
            try:
                basename = os.path.basename(img_path)
                
                # 이미지 유효성 검사
                if not validate_image(img_path):
                    result['failed_images'] += 1
                    continue
                
                # 이미지 분류 (착용컷/디테일컷)
                image_type = classify_image(img_path)
                
                # 의류 카테고리 분류
                try:
                    category, description, score = classify_clothing(img_path)
                    result['categories'][basename] = category
                    result['descriptions'][basename] = description
                except Exception as e:
                    logger.error(f"의류 분류 중 오류: {str(e)}")
                    result['categories'][basename] = "unknown"
                    result['descriptions'][basename] = "분류할 수 없는 이미지입니다."
                
                # 주요 색상 추출
                result['colors'][basename] = extract_dominant_colors(img_path, 3)
                
                # 메타데이터 추출
                result['metadata'][basename] = get_image_metadata(img_path)
                
                # 이미지를 해당 폴더로 복사
                dest_folder = wear_folder if image_type == "wear" else detail_folder
                shutil.copy2(img_path, os.path.join(dest_folder, basename))
                
                # 결과 목록에 추가
                if image_type == "wear":
                    result['wear'].append(basename)
                else:
                    result['detail'].append(basename)
                
                result['processed_images'] += 1
                
            except Exception as e:
                logger.error(f"이미지 {basename} 처리 중 오류: {str(e)}")
                result['failed_images'] += 1
        
        # 처리 완료 시간 기록
        result['end_time'] = datetime.now()
        result['processing_time'] = (result['end_time'] - result['start_time']).total_seconds()
        
        # 보고서 생성
        if generate_report:
            report_path = os.path.join(output_folder, "processing_report.json")
            with open(report_path, 'w', encoding='utf-8') as f:
                # datetime 객체를 직렬화 가능한 문자열로 변환
                result_copy = result.copy()
                result_copy['start_time'] = result_copy['start_time'].isoformat()
                result_copy['end_time'] = result_copy['end_time'].isoformat()
                json.dump(result_copy, f, ensure_ascii=False, indent=2)
        
        logger.info(f"일괄 처리 완료: {result['processed_images']}개 성공, {result['failed_images']}개 실패")
        return result
        
    except Exception as e:
        logger.error(f"일괄 처리 중 오류 발생: {str(e)}")
        result['end_time'] = datetime.now()
        return result

# 머신러닝 모델 캐싱 및 성능 최적화
_model_cache = {}

def get_cached_model(model_name: str) -> Any:
    """모델 캐싱을 통한 성능 향상"""
    if model_name not in _model_cache:
        if model_name == "hog":
            model = cv2.HOGDescriptor()
            model.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            _model_cache[model_name] = model
        # 다른 모델은 필요에 따라 추가
    
    return _model_cache.get(model_name)
