import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import streamlit as st


@st.cache_data
def load_data():
    df = pd.read_excel("data/perfume_database_cleaned.xlsx")
    df["notes"] = df["notes"].fillna("")
    return df


@st.cache_resource
def build_vectorizer(notes):
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(notes)
    return vectorizer, tfidf_matrix


df = load_data()
vectorizer, tfidf_matrix = build_vectorizer(df["notes"])


def recommend_perfume(perfume_name, top_n=5):
    if perfume_name not in df["perfume"].values:
        return ["Perfume not found"]

    idx = df[df["perfume"] == perfume_name].index[0]

    # Compute similarity ONLY for selected perfume
    similarity_scores = cosine_similarity(
        tfidf_matrix[idx], tfidf_matrix
    ).flatten()

    similar_indices = similarity_scores.argsort()[-top_n-1:-1][::-1]

    return df.iloc[similar_indices][["brand", "perfume", "notes"]]