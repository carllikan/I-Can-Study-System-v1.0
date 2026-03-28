import re
from operator import itemgetter

import math

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors


def preprocess_paragraph(paragraph):
    paragraph = re.sub('[^a-zA-Z0-9]', ' ', paragraph).lower()
    words = paragraph.split()
    return words


def jaccard_similarity(set1, set2):
    intersection = set(set1).intersection(set2)
    union = set(set1).union(set2)
    return len(intersection) / len(union)


def calculate_similarity(paragraph, keywords):
    paragraph_words = set(preprocess_paragraph(paragraph))
    similarity_scores = []
    for keyword_list in keywords:
        keyword_set = set(keyword_list)
        similarity = jaccard_similarity(paragraph_words, keyword_set)
        similarity_scores.append(similarity)
    return similarity_scores