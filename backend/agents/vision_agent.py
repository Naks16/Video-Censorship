"""
Vision Agent — Uses CLIP (ViT-B/32) to classify scenes and detect objects
in sampled frames. Also uses OpenCV Haar cascades for face count estimation.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from backend.agents.ingestion_agent import IngestionResult

logger = logging.getLogger(__name__)

# ── Scene and object prompt labels ────────────────────────────────────────────

SCENE_PROMPTS = [
    "an action / fight scene",
    "a romantic / love scene",
    "a dramatic / emotional scene",
    "a comedy / funny scene",
    "a horror / scary scene",
    "a song / dance sequence",
    "a car chase scene",
    "a crowd / gathering scene",
    "a family scene",
    "an outdoor / nature scene",
    "an urban / city scene",
    "a rural / village scene",
    "a sports scene",
    "a courtroom / legal scene",
    "a war / battlefield scene",
    "a hospital / medical scene",
    "a wedding scene",
    "a funeral scene",
    "a school / campus scene",
    "a prison scene",
]

OBJECT_PROMPTS = [
    "a weapon: gun, knife, or sword",
    "a vehicle: car, motorcycle, or truck",
    "a phone or computer",
    "food or drink",
    "money or jewelry",
    "fire or explosion",
    "a crowd of people",
    "an animal",
    "a building or architecture",
    "water: ocean, river, or rain",
]

# Singleton CLIP model cache
_clip_model = None
_clip_processor = None


def get_clip_model(model_name: str = "openai/clip-vit-base-patch32"):
    global _clip_model, _clip_processor
    if _clip_model is None:
        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor

            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"[Vision] Loading CLIP model on {device}")
            _clip_processor = CLIPProcessor.from_pretrained(model_name)
            _clip_model = CLIPModel.from_pretrained(model_name).to(device)
            _clip_model.eval()
            logger.info("[Vision] CLIP loaded successfully")
        except Exception as e:
            logger.error(f"[Vision] CLIP load failed: {e}")
            raise
    return _clip_model, _clip_processor


@dataclass
class VisionResult:
    top_scenes: List[Dict] = field(default_factory=list)     # [{scene, confidence, count}]
    detected_objects: List[str] = field(default_factory=list)
    face_count_avg: float = 0.0
    frames_analyzed: int = 0
    overall_confidence: float = 0.0
    errors: List[str] = field(default_factory=list)


class VisionAgent:
    """
    Analyzes sampled video frames using CLIP for scene/object classification
    and OpenCV for face detection.
    """

    def __init__(self) -> None:
        self.name = "vision"

    async def run(self, ingestion: IngestionResult) -> VisionResult:
        result = VisionResult()

        if not ingestion.frame_paths:
            msg = "[Vision] No frames available for analysis"
            logger.warning(msg)
            result.errors.append(msg)
            return result

        logger.info(f"[Vision] Analyzing {len(ingestion.frame_paths)} frames")

        try:
            result = await asyncio.to_thread(
                self._analyze_frames, ingestion.frame_paths, result
            )
        except Exception as e:
            logger.error(f"[Vision] Analysis failed: {e}")
            result.errors.append(str(e))

        return result

    def _analyze_frames(
        self, frame_paths: List[Path], result: VisionResult
    ) -> VisionResult:
        import torch
        from PIL import Image

        model, processor = get_clip_model()
        device = next(model.parameters()).device

        scene_scores: Dict[str, List[float]] = {s: [] for s in SCENE_PROMPTS}
        object_scores: Dict[str, List[float]] = {o: [] for o in OBJECT_PROMPTS}
        face_counts: List[int] = []

        # Pre-tokenize text prompts (only once)
        scene_inputs = processor(
            text=SCENE_PROMPTS, return_tensors="pt", padding=True
        ).to(device)
        object_inputs = processor(
            text=OBJECT_PROMPTS, return_tensors="pt", padding=True
        ).to(device)

        face_cascade = self._load_face_cascade()

        batch_size = 8
        frame_list = list(frame_paths)
        result.frames_analyzed = len(frame_list)

        with torch.no_grad():
            for i in range(0, len(frame_list), batch_size):
                batch_paths = frame_list[i : i + batch_size]
                images = []
                for fp in batch_paths:
                    try:
                        img = Image.open(fp).convert("RGB")
                        images.append(img)
                    except Exception:
                        continue

                if not images:
                    continue

                img_inputs = processor(
                    images=images, return_tensors="pt", padding=True
                ).to(device)

                # Image features
                image_features = model.get_image_features(**img_inputs)
                if hasattr(image_features, "image_embeds"):
                    image_features = image_features.image_embeds
                elif hasattr(image_features, "pooler_output"):
                    image_features = image_features.pooler_output
                
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)

                # Scene classification
                scene_text_features = model.get_text_features(**scene_inputs)
                if hasattr(scene_text_features, "text_embeds"):
                    scene_text_features = scene_text_features.text_embeds
                elif hasattr(scene_text_features, "pooler_output"):
                    scene_text_features = scene_text_features.pooler_output
                
                scene_text_features = scene_text_features / scene_text_features.norm(
                    dim=-1, keepdim=True
                )
                scene_similarity = (image_features @ scene_text_features.T) * model.logit_scale.exp()
                scene_probs = scene_similarity.softmax(dim=-1).cpu().numpy()

                for frame_probs in scene_probs:
                    for j, scene in enumerate(SCENE_PROMPTS):
                        scene_scores[scene].append(float(frame_probs[j]))

                # Object classification
                obj_text_features = model.get_text_features(**object_inputs)
                if hasattr(obj_text_features, "text_embeds"):
                    obj_text_features = obj_text_features.text_embeds
                elif hasattr(obj_text_features, "pooler_output"):
                    obj_text_features = obj_text_features.pooler_output
                
                obj_text_features = obj_text_features / obj_text_features.norm(
                    dim=-1, keepdim=True
                )
                obj_similarity = (image_features @ obj_text_features.T) * model.logit_scale.exp()
                obj_probs = obj_similarity.softmax(dim=-1).cpu().numpy()

                for frame_probs in obj_probs:
                    for j, obj in enumerate(OBJECT_PROMPTS):
                        object_scores[obj].append(float(frame_probs[j]))

                # Face detection
                if face_cascade is not None:
                    for fp in batch_paths:
                        count = self._count_faces(fp, face_cascade)
                        face_counts.append(count)

        # Aggregate scene results
        scene_averages = {
            scene: sum(scores) / len(scores)
            for scene, scores in scene_scores.items()
            if scores
        }
        top_scenes = sorted(scene_averages.items(), key=lambda x: -x[1])[:5]
        result.top_scenes = [
            {
                "scene": _clean_label(scene),
                "confidence": round(conf, 4),
            }
            for scene, conf in top_scenes
            if conf > 0.05
        ]

        # Detected objects (threshold 0.15)
        obj_averages = {
            obj: sum(scores) / len(scores)
            for obj, scores in object_scores.items()
            if scores
        }
        result.detected_objects = [
            _clean_label(obj)
            for obj, conf in obj_averages.items()
            if conf > 0.15
        ]

        # Face count
        result.face_count_avg = (
            sum(face_counts) / len(face_counts) if face_counts else 0.0
        )
        result.overall_confidence = (
            max(conf["confidence"] for conf in result.top_scenes)
            if result.top_scenes
            else 0.0
        )

        logger.info(
            f"[Vision] Top scenes: {[s['scene'] for s in result.top_scenes[:3]]}, "
            f"objects: {result.detected_objects[:3]}"
        )
        return result

    @staticmethod
    def _load_face_cascade():
        import cv2

        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            cascade = cv2.CascadeClassifier(cascade_path)
            return cascade if not cascade.empty() else None
        except Exception:
            return None

    @staticmethod
    def _count_faces(frame_path: Path, cascade) -> int:
        import cv2

        try:
            img = cv2.imread(str(frame_path))
            if img is None:
                return 0
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4)
            return len(faces)
        except Exception:
            return 0


def _clean_label(label: str) -> str:
    """Remove the 'a/an' prefix and trailing descriptors from prompt labels."""
    label = label.replace("an ", "").replace("a ", "").strip()
    # Take just the first part before '/'
    parts = label.split("/")
    return parts[0].strip().title()
