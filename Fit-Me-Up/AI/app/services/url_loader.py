# app/services/url_loader.py
# URL 한 장에 대해 face/body/skin 통합 분석
# -*- coding: utf-8 -*-
from __future__ import annotations

import io
from typing import Optional

import requests
import numpy as np
import cv2

from ..utils.image_io import load_image_bgr_from_bytes


class ImageDownloadError(Exception):
    pass


def fetch_image_bgr_from_url(image_url: str, timeout: float = 5.0) -> np.ndarray:
    """
    S3 등에서 호스팅되는 image_url을 받아서
    OpenCV BGR 이미지로 반환하는 헬퍼.

    - timeout: 다운로드 최대 대기 시간
    """
    try:
        resp = requests.get(image_url, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise ImageDownloadError(f"Failed to download image: {image_url}") from e

    # 기존 util 재사용
    bgr = load_image_bgr_from_bytes(resp.content)
    if bgr is None:
        raise ImageDownloadError(f"Cannot decode image: {image_url}")
    return bgr
