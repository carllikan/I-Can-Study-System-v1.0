import re
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


def knn_overlapping(paragraph, tags, keywords, k=1):
    similarity_scores = calculate_similarity(paragraph, keywords)
    sorted_scores = sorted(enumerate(similarity_scores), key=lambda x: x[1], reverse=True)

    avg_score = sum(similarity_scores) / len(similarity_scores)
    threshold_fraction = 0.75  # Set a fraction for the threshold (adjust as needed)
    threshold = threshold_fraction * avg_score

    top_k = [score_tuple for score_tuple in sorted_scores if score_tuple[1] >= threshold][:k]
    categories = [tags[index] for index, _ in top_k]
    return categories



def knn_2(paragraph, tags_2d, n_neighbors=1):
    keywords = []
    tags = []
    for tag in tags_2d:
        tags.append(tag[0])
        keywords.append(' '.join(tag[1]))

    vectorizer = TfidfVectorizer()

    vectorizer.fit(keywords)

    paragraph_vector = vectorizer.transform([paragraph])

    knn = NearestNeighbors(n_neighbors=n_neighbors)
    knn.fit(vectorizer.transform(keywords))

    distances, indices = knn.kneighbors(paragraph_vector)
    threshold = np.mean(distances)

    temp_d = distances[distances <= threshold]
    temp_i = indices[distances <= threshold]
    distances = temp_d
    indices = temp_i
    predicted_tags = [tags[index] for index in indices[0].flatten()]

    return predicted_tags
