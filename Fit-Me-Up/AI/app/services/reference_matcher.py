# app/services/reference_matcher.py
'''
    유저 벡터와 DB 내 연예인 프로필 벡터 간 cosine similarity 계산 후 Top-K 반환.
'''
import numpy as np

def cosine(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a)*np.linalg.norm(b) + 1e-8))

def match_user_to_references(user_vec, celeb_vectors, k=5):
    sims = [(cid, cosine(user_vec, vec)) for cid, vec in celeb_vectors.items()]
    sims.sort(key=lambda x: x[1], reverse=True)
    return sims[:k]
