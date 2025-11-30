# app/services/url_analyzer.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, Any

from .url_loader import fetch_image_bgr_from_url
from ..classifiers import face as face_mod
from ..classifiers import body as body_mod
from ..classifiers import skin as skin_mod


def analyze_image_from_url(image_url: str) -> Dict[str, Any]:
    """
    단일 image_url에 대해 face/body/skin classifier를 모두 실행.
    """
    bgr = fetch_image_bgr_from_url(image_url)

    face_res, _ = face_mod.classify(bgr, return_debug=False)
    body_res, _ = body_mod.classify(bgr, return_debug=False)
    skin_res, _ = skin_mod.classify(bgr, return_debug=False)

    return {
        "image_url": image_url,
        "face": face_res,
        "body": body_res,
        "skin": skin_res,
    }
