
---

# Plateforme d’Analyse de Contenu sur le Harcèlement

Un pipeline complet pour collecter, traiter et analyser les contenus liés au harcèlement sur les réseaux sociaux.

## 📋 Table des matières

* [Présentation générale](#présentation-générale)
* [Architecture du projet](#architecture-du-projet)
* [Étapes du pipeline](#étapes-du-pipeline)
* [Choix techniques](#choix-techniques)
* [Prérequis](#prérequis)
* [Installation](#installation)

## Présentation générale

Ce projet propose une solution complète pour analyser le harcèlement sur diverses plateformes sociales. Il collecte des données depuis Twitter, Reddit et Telegram, applique des traitements NLP (traitement du langage naturel) pour enrichir les contenus, puis les indexe dans Elasticsearch afin d’offrir des capacités avancées de recherche et de visualisation.

## Architecture du projet

```
Analyse-de-Contenu-sur-le-Harc-lement/
├── src/
│   ├── main/
│   │   ├── scrapers/           # Modules de collecte
│   │   │   ├── twitter_scraper.py
│   │   │   ├── reddit_scraper.py
│   │   │   ├── telegram_scraper.py
│   │   │   └── scraper.py      # Orchestration des scrapers
│   │   ├── processeing/        # Modules de traitement
│   │   │   ├── preprocessing.py  # Nettoyage et normalisation
│   │   │   └── nlp_pipeline.py   # Détection langue & sentiment
│   │   ├── migration/          # Migration de données
│   │   │   └── es_ingest.py    # Indexation Elasticsearch
│   │   └── main.py             # Orchestrateur principal
│   └── test/                   # Tests unitaires
│       ├── test_scraper.py
│       ├── test_preprocessing.py
│       └── test_nlp_pipeline.py
├── logs/                       # Journaux d'application
├── data/                       # Stockage des données
├── Dockerfile                  # Conteneurisation
├── docker-compose.yaml         # Orchestration multi-conteneurs
└── requirements.txt            # Dépendances Python
```

## Étapes du pipeline

### 1. Collecte de données

* Extraire des contenus liés au harcèlement sur Twitter (API v2), Reddit (subreddits ciblés) et Telegram (groupes publics).
* Stocker les données brutes dans MongoDB (`posts`).

### 2. Prétraitement

* **Nettoyage multi-étapes** :
  * Suppression des balises HTML via expressions régulières
  * Élimination des URLs (http, https, www)
  * Retrait des caractères spéciaux, de la ponctuation et des chiffres
  * Conversion en minuscules pour uniformisation
* **Traitement linguistique** :
  * Tokenisation du texte (découpage en mots individuels)
  * Filtrage des stopwords en français ET en anglais
  * Élimination des mots trop courts (< 3 caractères)
  * Lemmatisation via NLTK WordNetLemmatizer (réduction à la forme canonique)
* **Traitement par lots** :
  * Suivi de progression en temps réel (logs tous les 100 documents)
  * Traitement séparé du titre et du contenu
  * Conservation des métadonnées (auteur, date, URL)
* **Persistance optimisée** :
  * Sauvegarde dans MongoDB avec indexation sur URL
  * Mécanisme d'upsert pour éviter les doublons
  * Structure document original + version prétraitée

### 3. Traitement NLP

* **Détection de langue** :
  * Utilisation de la bibliothèque LangDetect
  * Analyse des 1000 premiers caractères pour efficacité
  * Gestion des cas spéciaux (textes courts, erreurs de détection)
  * Support multilingue avec priorité français/anglais
* **Analyse de sentiment** :
  * Utilisation de TextBlob avec adaptation multilingue
  * Calcul de polarité sur échelle normalisée (-1 à 1)
  * Classification en trois catégories :
    * Positif (polarité > 0.1)
    * Négatif (polarité < -0.1)
    * Neutre (-0.1 ≤ polarité ≤ 0.1)
  * Prise en compte du contexte linguistique
* **Enrichissement des données** :
  * Ajout des champs `langue` et `sentiment` à chaque document
  * Conservation du score numérique de polarité pour analyses fines
  * Horodatage du traitement (`enriched_at`)
* **Intégration et extensibilité** :
  * Système de traitement modulaire
  * Possibilité d'export vers CSV pour analyses externes
  * Architecture permettant l'ajout de nouvelles analyses (entités nommées, classification, etc.)

### 4. Indexation Elasticsearch

* Créer un index `harcelement_posts` avec mapping adapté.
* Transformer et indexer les documents par lots.
* Indexer les champs : titre, contenu, auteur, date, URL, langue, sentiment, score.

### 5. Visualisation avec Kibana

* Explorer via dashboards interactifs.
* Visualiser la répartition des sentiments.
* Effectuer des recherches avancées.
* Générer des rapports sur les tendances du harcèlement.

## Choix techniques

### Langages & outils

* **Python 3.9** : riche écosystème NLP.
* **MongoDB** : flexible pour données non structurées.
* **Elasticsearch & Kibana** : recherche et visualisation avancées.

### Bibliothèques principales

* Tweepy (Twitter API), AsyncPRAW (Reddit), Telethon (Telegram)
* NLTK, TextBlob, LangDetect pour NLP.

### Conteneurisation

* Docker & Docker Compose pour déploiement cohérent.

### Architecture

* Modulaire et asynchrone pour efficacité.
* Journalisation étendue pour débogage.

### Mapping Elasticsearch

* Champs texte avec sous-champs `.keyword` pour agrégation.
* Champs `keyword` pour auteur, langue, sentiment.
* Analyseur standard multilingue.

## Prérequis

* Python 3.9+
* Docker & Docker Compose
* Clés API Twitter, Reddit, Telegram

## Installation 

1. Cloner le dépôt :

```bash
git clone https://github.com/votrenomdutilisateur/Smart-Conseil.git
cd Smart-Conseil
```

2. Créer un fichier `.env` avec vos identifiants API :

```
TWITTER_BEARER_TOKEN=...
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
TELEGRAM_PHONE=...
```

3. Construire et lancer les conteneurs :

```bash
docker-compose up -d
```

---

