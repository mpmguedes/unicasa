#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
UniCasa - Agregador de Quartos para Estudantes
                    Porto | Lisboa | Coimbra
===============================================================================

INSTALACAO EM WINDOWS:
1. Abrir o Prompt de Comando (cmd) ou PowerShell
2. Criar ambiente virtual (recomendado):
   python -m venv venv
   venv\Scripts\activate
3. Instalar dependencias:
   pip install flask feedparser geopy haversine beautifulsoup4 lxml requests
   pip install playwright
   playwright install chromium
   # OU para Camoufox (browser anti-bot):
   pip install camoufox
   python -m camoufox fetch
4. Executar a aplicacao:
   python app.py
5. Abrir o browser em: http://127.0.0.1:5000
===============================================================================
"""

import re
import math
import time
import html
import random
import hashlib
import requests
import json
import feedparser
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
from collections import OrderedDict

from flask import Flask, request, jsonify
from flask import render_template_string
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from bs4 import BeautifulSoup

# =============================================================================
# CONFIGURACAO DAS FACULDADES POR CIDADE
# =============================================================================
CIDADES = {
    "Porto": OrderedDict([
        ("FEUP - Polo da Asprela",           {"lat": 41.1785, "lon": -8.5950}),
        ("FEP - Faculdade de Economia",       {"lat": 41.1620, "lon": -8.6260}),
        ("FBAUP - Belas Artes",               {"lat": 41.1494, "lon": -8.6130}),
        ("FAUP - Arquitetura",                {"lat": 41.1470, "lon": -8.6140}),
        ("FLUP - Letras",                     {"lat": 41.1610, "lon": -8.6000}),
        ("ISEP - Instituto Superior Engenharia", {"lat": 41.1810, "lon": -8.6040}),
        ("ESMAE - Escola Musica Artes Espetaculo", {"lat": 41.1480, "lon": -8.6100}),
        ("Catolica Porto",                    {"lat": 41.1550, "lon": -8.6290}),
        ("FMUP - Medicina",                   {"lat": 41.1458, "lon": -8.6170}),
        ("FCUP - Ciencias",                   {"lat": 41.1462, "lon": -8.6165}),
        ("FDUP - Direito",                    {"lat": 41.1455, "lon": -8.6155}),
        ("FPCEUP - Psicologia",               {"lat": 41.1468, "lon": -8.6145}),
        ("FADEUP - Desporto",                 {"lat": 41.1835, "lon": -8.5920}),
        ("ICBAS - Ciencias Biomedicas",       {"lat": 41.1450, "lon": -8.6180}),
        ("ESE - Escola Superior Educacao",    {"lat": 41.1600, "lon": -8.6050}),
        ("ESTSP - Saude do Porto",            {"lat": 41.1555, "lon": -8.6120}),
        ("ISCAP - Contabilidade e Administracao", {"lat": 41.1590, "lon": -8.6080}),
    ]),
    "Lisboa": OrderedDict([
        ("IST - Alameda",                     {"lat": 38.7368, "lon": -9.1393}),
        ("IST - Taguspark",                   {"lat": 38.7370, "lon": -9.3030}),
        ("FCUL - Ciencias",                   {"lat": 38.7560, "lon": -9.1580}),
        ("FFLUL - Letras",                    {"lat": 38.7520, "lon": -9.1580}),
        ("FBAUL - Belas Artes",               {"lat": 38.7070, "lon": -9.1450}),
        ("FMUL - Medicina",                   {"lat": 38.7480, "lon": -9.1590}),
        ("FDUL - Direito",                    {"lat": 38.7525, "lon": -9.1575}),
        ("ISEG - Economia",                   {"lat": 38.7065, "lon": -9.1525}),
        ("ISCTE-IUL",                         {"lat": 38.7480, "lon": -9.1535}),
        ("FCSH - Ciencias Sociais",           {"lat": 38.7570, "lon": -9.1530}),
        ("NOVA SBE",                          {"lat": 38.7320, "lon": -9.1490}),
        ("ISA - Agronomia",                   {"lat": 38.7260, "lon": -9.1830}),
        ("FMD - Medicina Dentaria",           {"lat": 38.7485, "lon": -9.1585}),
        ("FARMACIA ULisboa",                  {"lat": 38.7565, "lon": -9.1575}),
        ("ESAD.CR - Artes",                   {"lat": 38.7100, "lon": -9.1400}),
        ("Lusofona",                          {"lat": 38.7200, "lon": -9.1450}),
    ]),
    "Coimbra": OrderedDict([
        ("UC - Letras",                       {"lat": 40.2090, "lon": -8.4240}),
        ("UC - Direito",                      {"lat": 40.2070, "lon": -8.4250}),
        ("UC - Medicina",                     {"lat": 40.2150, "lon": -8.4100}),
        ("FCTUC - Ciencias e Tecnologia",     {"lat": 40.1860, "lon": -8.4150}),
        ("FEUC - Economia",                   {"lat": 40.2050, "lon": -8.4200}),
        ("FPCE - Psicologia",                 {"lat": 40.2100, "lon": -8.4220}),
        ("FCDE - Desporto",                   {"lat": 40.2080, "lon": -8.4180}),
        ("FLUC - Farmacia",                   {"lat": 40.2110, "lon": -8.4230}),
        ("IPC - Politecnico",                 {"lat": 40.2030, "lon": -8.4180}),
        ("ESAC - Agraria",                    {"lat": 40.1980, "lon": -8.4250}),
        ("ISCAC - Contabilidade",             {"lat": 40.2120, "lon": -8.4200}),
        ("ESTESC - Saude",                    {"lat": 40.2000, "lon": -8.4150}),
    ]),
}

NOMES_CIDADES = list(CIDADES.keys())

# =============================================================================
# ZONAS POR CIDADE - CLASSIFICACAO
# =============================================================================
ZONAS = {
    "Porto": {
        "Paranhos": {"seguranca": 8, "ruido": 5, "comercio": 7, "metro_min": 5, "bus_min": 3, "comboio_min": 20, "lat": 41.1750, "lon": -8.6000},
        "Cedofeita": {"seguranca": 8, "ruido": 7, "comercio": 9, "metro_min": 8, "bus_min": 5, "comboio_min": 15, "lat": 41.1550, "lon": -8.6200},
        "Bonfim": {"seguranca": 7, "ruido": 6, "comercio": 7, "metro_min": 7, "bus_min": 4, "comboio_min": 12, "lat": 41.1500, "lon": -8.6050},
        "Ramalde": {"seguranca": 8, "ruido": 4, "comercio": 6, "metro_min": 10, "bus_min": 6, "comboio_min": 18, "lat": 41.1650, "lon": -8.6400},
        "Aldoar": {"seguranca": 9, "ruido": 3, "comercio": 5, "metro_min": 12, "bus_min": 7, "comboio_min": 22, "lat": 41.1850, "lon": -8.6500},
        "Massarelos": {"seguranca": 7, "ruido": 6, "comercio": 7, "metro_min": 6, "bus_min": 4, "comboio_min": 10, "lat": 41.1480, "lon": -8.6250},
        "Miragaia": {"seguranca": 6, "ruido": 7, "comercio": 6, "metro_min": 9, "bus_min": 5, "comboio_min": 14, "lat": 41.1450, "lon": -8.6200},
        "Foz": {"seguranca": 9, "ruido": 3, "comercio": 6, "metro_min": 15, "bus_min": 8, "comboio_min": 12, "lat": 41.1550, "lon": -8.6750},
        "Campanha": {"seguranca": 5, "ruido": 7, "comercio": 6, "metro_min": 5, "bus_min": 3, "comboio_min": 3, "lat": 41.1500, "lon": -8.5850},
        "Boavista": {"seguranca": 8, "ruido": 6, "comercio": 9, "metro_min": 7, "bus_min": 4, "comboio_min": 14, "lat": 41.1580, "lon": -8.6300},
        "Lordelo do Ouro": {"seguranca": 8, "ruido": 4, "comercio": 6, "metro_min": 11, "bus_min": 6, "comboio_min": 16, "lat": 41.1480, "lon": -8.6400},
        "Antas": {"seguranca": 7, "ruido": 5, "comercio": 6, "metro_min": 6, "bus_min": 4, "comboio_min": 8, "lat": 41.1550, "lon": -8.5900},
        "Matosinhos Centro": {"seguranca": 8, "ruido": 5, "comercio": 8, "metro_min": 10, "bus_min": 5, "comboio_min": 18, "lat": 41.1850, "lon": -8.6600},
        "Maia Centro": {"seguranca": 7, "ruido": 4, "comercio": 7, "metro_min": 14, "bus_min": 8, "comboio_min": 20, "lat": 41.2300, "lon": -8.6200},
        "Gondomar": {"seguranca": 7, "ruido": 4, "comercio": 5, "metro_min": 16, "bus_min": 9, "comboio_min": 22, "lat": 41.1400, "lon": -8.5300},
        "Vila Nova de Gaia Centro": {"seguranca": 7, "ruido": 6, "comercio": 8, "metro_min": 8, "bus_min": 5, "comboio_min": 10, "lat": 41.1350, "lon": -8.6100},
    },
    "Lisboa": {
        "Alameda": {"seguranca": 7, "ruido": 7, "comercio": 8, "metro_min": 3, "bus_min": 2, "comboio_min": 15, "lat": 38.7360, "lon": -9.1330},
        "Avenidas Novas": {"seguranca": 8, "ruido": 6, "comercio": 9, "metro_min": 4, "bus_min": 3, "comboio_min": 10, "lat": 38.7300, "lon": -9.1450},
        "Saldanha": {"seguranca": 8, "ruido": 7, "comercio": 9, "metro_min": 3, "bus_min": 2, "comboio_min": 8, "lat": 38.7350, "lon": -9.1450},
        "Arroios": {"seguranca": 6, "ruido": 7, "comercio": 8, "metro_min": 4, "bus_min": 3, "comboio_min": 12, "lat": 38.7250, "lon": -9.1350},
        "Intendente": {"seguranca": 5, "ruido": 7, "comercio": 7, "metro_min": 3, "bus_min": 2, "comboio_min": 10, "lat": 38.7200, "lon": -9.1350},
        "Graça": {"seguranca": 6, "ruido": 6, "comercio": 7, "metro_min": 6, "bus_min": 4, "comboio_min": 15, "lat": 38.7150, "lon": -9.1250},
        "Penha": {"seguranca": 5, "ruido": 6, "comercio": 5, "metro_min": 8, "bus_min": 5, "comboio_min": 18, "lat": 38.7100, "lon": -9.1200},
        "Belém": {"seguranca": 8, "ruido": 4, "comercio": 6, "metro_min": 12, "bus_min": 6, "comboio_min": 5, "lat": 38.6950, "lon": -9.2000},
        "Campo Grande": {"seguranca": 7, "ruido": 5, "comercio": 7, "metro_min": 5, "bus_min": 3, "comboio_min": 8, "lat": 38.7600, "lon": -9.1550},
        "Benfica": {"seguranca": 6, "ruido": 5, "comercio": 6, "metro_min": 8, "bus_min": 5, "comboio_min": 10, "lat": 38.7450, "lon": -9.2000},
        "Chelas": {"seguranca": 4, "ruido": 7, "comercio": 5, "metro_min": 7, "bus_min": 4, "comboio_min": 15, "lat": 38.7350, "lon": -9.1100},
        "Alvalade": {"seguranca": 8, "ruido": 5, "comercio": 8, "metro_min": 5, "bus_min": 3, "comboio_min": 8, "lat": 38.7500, "lon": -9.1500},
        "Parque das Nações": {"seguranca": 9, "ruido": 4, "comercio": 7, "metro_min": 5, "bus_min": 5, "comboio_min": 3, "lat": 38.7600, "lon": -9.0900},
        "Estrela": {"seguranca": 8, "ruido": 5, "comercio": 8, "metro_min": 6, "bus_min": 4, "comboio_min": 12, "lat": 38.7100, "lon": -9.1550},
        "Santos": {"seguranca": 7, "ruido": 7, "comercio": 8, "metro_min": 5, "bus_min": 3, "comboio_min": 10, "lat": 38.7050, "lon": -9.1500},
        "Lapa": {"seguranca": 8, "ruido": 5, "comercio": 7, "metro_min": 7, "bus_min": 4, "comboio_min": 10, "lat": 38.7150, "lon": -9.1600},
        "Anjos": {"seguranca": 6, "ruido": 7, "comercio": 7, "metro_min": 4, "bus_min": 3, "comboio_min": 10, "lat": 38.7200, "lon": -9.1300},
    },
    "Coimbra": {
        "Alta Universitaria": {"seguranca": 8, "ruido": 4, "comercio": 7, "metro_min": 0, "bus_min": 2, "comboio_min": 20, "lat": 40.2080, "lon": -8.4250},
        "Baixa": {"seguranca": 7, "ruido": 7, "comercio": 8, "metro_min": 0, "bus_min": 2, "comboio_min": 15, "lat": 40.2100, "lon": -8.4300},
        "Celas": {"seguranca": 7, "ruido": 5, "comercio": 6, "metro_min": 0, "bus_min": 4, "comboio_min": 10, "lat": 40.2150, "lon": -8.4200},
        "Santa Clara": {"seguranca": 8, "ruido": 3, "comercio": 5, "metro_min": 0, "bus_min": 5, "comboio_min": 12, "lat": 40.2050, "lon": -8.4400},
        "Solum": {"seguranca": 7, "ruido": 4, "comercio": 5, "metro_min": 0, "bus_min": 6, "comboio_min": 8, "lat": 40.1950, "lon": -8.4300},
        "Tovim": {"seguranca": 7, "ruido": 4, "comercio": 4, "metro_min": 0, "bus_min": 7, "comboio_min": 15, "lat": 40.2200, "lon": -8.4150},
        "Botanica": {"seguranca": 8, "ruido": 3, "comercio": 5, "metro_min": 0, "bus_min": 5, "comboio_min": 18, "lat": 40.2000, "lon": -8.4250},
        "S. Martinho": {"seguranca": 6, "ruido": 4, "comercio": 4, "metro_min": 0, "bus_min": 8, "comboio_min": 10, "lat": 40.1850, "lon": -8.4400},
        "Portela": {"seguranca": 7, "ruido": 5, "comercio": 6, "metro_min": 0, "bus_min": 4, "comboio_min": 12, "lat": 40.1950, "lon": -8.4200},
        "Lousã": {"seguranca": 8, "ruido": 2, "comercio": 4, "metro_min": 0, "bus_min": 10, "comboio_min": 20, "lat": 40.1150, "lon": -8.2500},
    },
}

ZONA_KEYWORDS = {
    "Porto": {
        "Paranhos": ["paranhos", "polo", "asprela", "hospital sao joao", "s. joao"],
        "Cedofeita": ["cedofeita", "carlos alberto", "praca parada leitao"],
        "Bonfim": ["bonfim", "campo 24 de agosto", "conde agueda"],
        "Ramalde": ["ramalde", "viso", "circunvalacao"],
        "Aldoar": ["aldoar", "foz do douro", "monte da virgem", "nevogilde"],
        "Massarelos": ["massarelos", "jardim palacio cristal"],
        "Miragaia": ["miragaia", "ribeira", "alfandega"],
        "Foz": ["foz", "passeio alegre", "castelo do queijo"],
        "Campanha": ["campanha", "campanhã", "estacao campanha", "sao roque"],
        "Boavista": ["boavista", "praca mouzinho", "casa da musica"],
        "Lordelo do Ouro": ["lordelo", "afurada", "passeio das virtudes"],
        "Antas": ["antas", "dragon stadium", "estadio dragao"],
        "Matosinhos Centro": ["matosinhos", "mercado", "praia"],
        "Maia Centro": ["maia", "forum maia", "pedras rubras"],
        "Gondomar": ["gondomar", "rio tinto", "valbom"],
        "Vila Nova de Gaia Centro": ["gaia", "jardim morro", "caves vinho", "serra pilar"],
    },
    "Lisboa": {
        "Alameda": ["alameda", "arco do cego", "instituto superior tecnico"],
        "Avenidas Novas": ["avenidas novas", "sao sebastiao", "picoas"],
        "Saldanha": ["saldanha", "duque de palmela", "fontes pereira"],
        "Arroios": ["arroios", "anjos", "intendente"],
        "Intendente": ["intendente", "martim moniz"],
        "Graça": ["graca", "vila berta", "sao vicente"],
        "Penha": ["penha", "beato"],
        "Belém": ["belem", "padrao descobrimentos", "torre belem"],
        "Campo Grande": ["campo grande", "entrecampos", "zoo"],
        "Benfica": ["benfica", "estadio da luz", "coloane"],
        "Chelas": ["chelas", "marvila", "beato"],
        "Alvalade": ["alvalade", "campo grande", "republica"],
        "Parque das Nações": ["naccoes", "nations", "orient", "vasco da gama"],
        "Estrela": ["estrela", "rato", "santos"],
        "Santos": ["santos", "cais sodre", "lapa"],
        "Lapa": ["lapa", "estrela", "santo condestavel"],
        "Anjos": ["anjos", "intendente", "arroios"],
    },
    "Coimbra": {
        "Alta Universitaria": ["alta", "universidade", "paco das escolas", "joanina"],
        "Baixa": ["baixa", "ferreira borges", "santa cruz"],
        "Celas": ["celas", "jardim botanico"],
        "Santa Clara": ["santa clara", "convento", "quinta das lagrimas"],
        "Solum": ["solum", "downtown"],
        "Tovim": ["tovim", "cemiterio"],
        "Botanica": ["botanica", "jardim botanico"],
        "S. Martinho": ["martinho", "bispo"],
        "Portela": ["portela", "ponte"],
        "Lousã": ["lousa", "lousã"],
    },
}

# =============================================================================
# CACHE GLOBAL (por cidade)
# =============================================================================
CACHE = {
    "Porto": {"anuncios": None, "timestamp": None, "fonte": None},
    "Lisboa": {"anuncios": None, "timestamp": None, "fonte": None},
    "Coimbra": {"anuncios": None, "timestamp": None, "fonte": None},
}
CACHE_TTL = 15 * 60
MAX_PAGES = 5

GEOCODER = Nominatim(user_agent="unicasa_app_v1")
GEOCODER_CACHE = {}

# =============================================================================
# FUNCOES AUXILIARES
# =============================================================================

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def extrair_preco(texto):
    if not texto:
        return None
    padroes = [
        r'([\d\.]+,?\d*)\s*[€\s]',
        r'([\d\.]+,?\d*)\s*EUR',
        r'€\s*([\d\.]+,?\d*)',
    ]
    for padrao in padroes:
        m = re.search(padrao, texto, re.IGNORECASE)
        if m:
            s = m.group(1).replace('.', '').replace(',', '.')
            try:
                v = float(s)
                return v if v < 5000 else None
            except ValueError:
                continue
    return None


def determinar_zona(titulo, descricao, cidade):
    texto = f"{titulo} {descricao}".lower()
    keywords = ZONA_KEYWORDS.get(cidade, {})
    for zona, kws in keywords.items():
        for kw in kws:
            if kw in texto:
                return zona
    return None


def geocodificar_endereco(endereco, cidade):
    if not endereco:
        return None, None
    chave = hashlib.md5(f"{endereco}-{cidade}".encode('utf-8')).hexdigest()
    if chave in GEOCODER_CACHE:
        return GEOCODER_CACHE[chave]
    try:
        loc = GEOCODER.geocode(f"{endereco}, {cidade}, Portugal", timeout=10)
        if loc:
            resultado = (loc.latitude, loc.longitude)
            GEOCODER_CACHE[chave] = resultado
            return resultado
    except (GeocoderTimedOut, GeocoderServiceError):
        pass
    zona = determinar_zona(endereco, "", cidade)
    zonas_cidade = ZONAS.get(cidade, {})
    if zona and zona in zonas_cidade:
        z = zonas_cidade[zona]
        resultado = (z["lat"], z["lon"])
        GEOCODER_CACHE[chave] = resultado
        return resultado
    return None, None


def calcular_distancia_faculdade(lat, lon, faculdade_nome, cidade):
    if not all([lat, lon, faculdade_nome, cidade]) or cidade not in CIDADES:
        return None
    facs = CIDADES[cidade]
    if faculdade_nome not in facs:
        return None
    f = facs[faculdade_nome]
    return round(haversine(lat, lon, f["lat"], f["lon"]), 1)


def estrelas_html(nota):
    cheias = int(round(nota / 2))
    vazias = 5 - cheias
    return "★" * cheias + "☆" * vazias


def badge_nota(nota):
    if nota >= 8:
        return "nota-boa"
    if nota >= 5:
        return "nota-media"
    return "nota-mau"


def extrair_data_disponibilidade(titulo, descricao=""):
    texto = f"{titulo} {descricao}".lower()
    meses = {
        "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4,
        "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
        "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
        "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
        "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
    }
    ano_atual = datetime.now().year

    padrao1 = re.search(r'dispon[ií]vel\s+(?:a\s+partir\s+de|desde|em|para)\s+(\w+)\s*(\d{4})?', texto, re.IGNORECASE)
    if padrao1:
        mes_str = padrao1.group(1).lower()
        ano_str = padrao1.group(2)
        if mes_str in meses:
            ano = int(ano_str) if ano_str else ano_atual
            return f"Disponivel em {mes_str.capitalize()} {ano}"

    padrao2 = re.search(r'a\s+partir\s+de\s+(\w+)\s*(\d{4})?', texto, re.IGNORECASE)
    if padrao2:
        mes_str = padrao2.group(1).lower()
        ano_str = padrao2.group(2)
        if mes_str in meses:
            ano = int(ano_str) if ano_str else ano_atual
            return f"A partir de {mes_str.capitalize()} {ano}"

    for mes_str, mes_num in meses.items():
        padrao = re.search(rf'\b{mes_str}\b\.?\s*(\d{{4}})?', texto, re.IGNORECASE)
        if padrao:
            ano_str = padrao.group(1)
            ano = int(ano_str) if ano_str else ano_atual
            return f"Disponivel em {mes_str.capitalize()} {ano}"

    if re.search(r'\b(imediatamente|pronto|j[aá]\b|dispon[ií]vel\s+j[aá])', texto, re.IGNORECASE):
        return "Disponivel imediatamente"
    if re.search(r'\b(entrada\s+imediata|entra\s+j[aá])', texto, re.IGNORECASE):
        return "Entrada imediata"

    return None


# =============================================================================
# WEB SCRAPING - IMOVIRTUAL (fonte principal - funciona bem)
# =============================================================================

def fetch_imovirtual_scraping(cidade, pagina=1):
    """Faz scraping de uma pagina especifica do Imovirtual."""
    slug = cidade.lower()
    if pagina == 1:
        url = f"https://www.imovirtual.com/pt/resultados/arrendar/quarto/{slug}/{slug}"
    else:
        url = f"https://www.imovirtual.com/pt/resultados/arrendar/quarto/{slug}/{slug}?page={pagina}"
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"),
        "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        anuncios = []
        container = soup.find("div", {"data-cy": "search.listing.organic"})
        if not container:
            container = soup
        articles = container.find_all("article", limit=40)
        zonas_cidade = ZONAS.get(cidade, {})
        for art in articles:
            try:
                all_ps = art.find_all("p")
                titulo = f"Quarto em {cidade}"
                local = cidade
                for p in all_ps:
                    txt = p.get_text(strip=True)
                    if re.match(r'^\d+\s*/\s*\d+$', txt):
                        continue
                    if titulo == f"Quarto em {cidade}":
                        if 'quarto' in txt.lower() or 'alugo' in txt.lower() or 'arrenda' in txt.lower():
                            titulo = txt
                            continue
                    if ',' in txt or any(z.lower() in txt.lower() for z in zonas_cidade):
                        if txt != titulo:
                            local = txt
                            break

                link = ""
                for a in art.find_all("a", href=True):
                    href = a["href"]
                    if href.startswith("/pt/anuncio/") or "imovirtual.com" in href:
                        link = urljoin("https://www.imovirtual.com", href)
                        break

                preco = None
                for sp in art.find_all("span"):
                    txt = sp.get_text(strip=True)
                    if "€" in txt and "/m" not in txt.lower():
                        preco = extrair_preco(txt)
                        if preco:
                            break

                if preco is None:
                    continue

                desc = local
                for sp in art.find_all("span"):
                    txt = sp.get_text(strip=True)
                    if "m²" in txt and txt not in desc:
                        desc += f" | {txt}"
                        break

                zona = determinar_zona(titulo, local, cidade)
                if not zona:
                    for z in zonas_cidade:
                        if z.lower() in local.lower():
                            zona = z
                            break

                disponivel = extrair_data_disponibilidade(titulo, desc)

                img = ""
                img_tag = art.find("img", {"data-cy": "listing-item-image-source"})
                if img_tag:
                    img = img_tag.get("src", "")
                if not img:
                    img_tag = art.find("img")
                    if img_tag:
                        img = img_tag.get("src", "")

                lat, lon = None, None
                if zona and zona in zonas_cidade:
                    zd = zonas_cidade[zona]
                    lat, lon = zd["lat"], zd["lon"]

                anuncios.append({
                    "titulo": titulo,
                    "preco": preco,
                    "descricao": desc,
                    "link": link,
                    "data": datetime.now().strftime("%Y-%m-%d"),
                    "disponivel": disponivel,
                    "lat": lat,
                    "lon": lon,
                    "zona": zona,
                    "fonte": "Imovirtual",
                    "imagem": img,
                })
            except Exception:
                continue
        return anuncios
    except Exception as e:
        print(f"[Scraping] Erro Imovirtual {cidade} pag {pagina}: {e}")
        return []


def fetch_imovirtual_todas_paginas(cidade):
    """Varre multiplas paginas do Imovirtual e junta os resultados."""
    todos = []
    for pagina in range(1, MAX_PAGES + 1):
        print(f"[Scraping] Imovirtual {cidade} - pagina {pagina}/{MAX_PAGES}...")
        anuncios = fetch_imovirtual_scraping(cidade, pagina)
        if not anuncios:
            print(f"[Scraping] Pagina {pagina} vazia, a parar.")
            break
        todos.extend(anuncios)
        print(f"[Scraping] Pagina {pagina}: {len(anuncios)} anuncios")
        if pagina < MAX_PAGES:
            time.sleep(0.5)
    return todos


# =============================================================================
# WEB SCRAPING - CUSTOJUSTO (via JSON Next.js - nao precisa de Playwright!)
# =============================================================================

def fetch_custojusto_scraping(cidade, max_anuncios=40):
    """Extrai anuncios do CustoJusto via JSON embutido do Next.js."""
    slug = cidade.lower()
    url = f"https://www.custojusto.pt/{slug}/imobiliario/quartos"
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"),
        "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        next_data = soup.find("script", id="__NEXT_DATA__")
        if not next_data:
            print(f"[CustoJusto] JSON nao encontrado para {cidade}")
            return []

        data = json.loads(next_data.string)
        list_items = data.get("props", {}).get("pageProps", {}).get("listItems", [])

        anuncios = []
        zonas_cidade = ZONAS.get(cidade, {})

        for item in list_items[:max_anuncios]:
            try:
                titulo = item.get("title", "")
                if not titulo:
                    continue

                preco = item.get("price")
                if isinstance(preco, str):
                    preco = preco.replace("€", "").replace(".", "").replace(",", ".").strip()
                    try:
                        preco = float(preco)
                    except ValueError:
                        continue
                if not preco or preco < 50 or preco > 5000:
                    continue

                link = item.get("url", "")
                if link.startswith("/"):
                    link = f"https://www.custojusto.pt{link}"

                desc = item.get("body", "")[:200]

                loc_data = item.get("locationNames", {})
                local = ""
                if isinstance(loc_data, dict):
                    parts = []
                    for key in ["parish", "county", "district"]:
                        if loc_data.get(key):
                            parts.append(loc_data[key])
                    local = ", ".join(parts)
                elif isinstance(loc_data, list) and loc_data:
                    local = ", ".join(str(x) for x in loc_data)
                if not local:
                    local = cidade

                img = item.get("imageFullURL", "")
                list_time = item.get("listTime", "")

                zona = determinar_zona(titulo, desc + " " + local, cidade)
                if not zona:
                    for z in zonas_cidade:
                        if z.lower() in local.lower() or z.lower() in titulo.lower():
                            zona = z
                            break

                lat, lon = None, None
                if zona and zona in zonas_cidade:
                    zd = zonas_cidade[zona]
                    lat, lon = zd["lat"], zd["lon"]

                anuncios.append({
                    "titulo": titulo,
                    "preco": preco,
                    "descricao": desc or local,
                    "link": link,
                    "data": list_time or datetime.now().strftime("%Y-%m-%d"),
                    "disponivel": None,
                    "lat": lat,
                    "lon": lon,
                    "zona": zona,
                    "fonte": "CustoJusto",
                    "imagem": img,
                })
            except Exception:
                continue

        print(f"[CustoJusto] {cidade}: {len(anuncios)} anuncios")
        return anuncios

    except Exception as e:
        print(f"[CustoJusto] Erro {cidade}: {e}")
        return []


# =============================================================================
# UNIPLACES (desativado - site usa JS pesado)
# =============================================================================

def fetch_uniplaces_scraping(cidade, max_anuncios=20):
    return []


# =============================================================================
# ERASMUSINN (desativado - 404)
# =============================================================================

def fetch_erasmusinn_scraping(cidade, max_anuncios=20):
    return []




# =============================================================================
# WEB SCRAPING - HOUSINGANYWHERE (popular entre estudantes Erasmus)
# =============================================================================

def fetch_housinganywhere(cidade, max_anuncios=20):
    """Extrai anuncios do HousingAnywhere - muito popular entre estudantes."""
    urls = {
        "Porto": "https://housinganywhere.com/Porto--Portugal",
        "Lisboa": "https://housinganywhere.com/Lisbon--Portugal",
        "Coimbra": "https://housinganywhere.com/Coimbra--Portugal",
    }
    url = urls.get(cidade)
    if not url:
        return []

    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"),
        "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        links = soup.find_all("a", href=re.compile(r"/room/"))
        anuncios = []
        vistos = set()
        zonas_cidade = ZONAS.get(cidade, {})

        for a in links[:max_anuncios]:
            try:
                href = a.get("href", "")
                if href in vistos:
                    continue
                vistos.add(href)

                if not href.startswith("http"):
                    link = "https://housinganywhere.com" + href
                else:
                    link = href

                txt = a.get_text(strip=True)

                # Extrair preco - formato: €1050/month
                preco = None
                m = re.search(r'€([\d\s]+)/month', txt)
                if m:
                    s = m.group(1).replace(' ', '').replace('.', '').replace(',', '.')
                    try:
                        preco = float(s)
                    except ValueError:
                        continue
                if not preco or preco < 100 or preco > 5000:
                    continue

                # Titulo - texto antes do preco
                titulo = txt[:200]

                # Localizacao
                local = cidade
                m2 = re.search(r'(?:in|Private room in|Studio in|Apartment in|House in)\s+([^€•]+?)(?:\d+\s*m²|•|$)', txt, re.IGNORECASE)
                if m2:
                    local = m2.group(1).strip()[:80]

                # Disponibilidade
                disp = None
                m3 = re.search(r'Available\s+(now|from\s+\d+\s+\w+|from\s+\w+)', txt, re.IGNORECASE)
                if m3:
                    disp = "Disponivel " + m3.group(1)

                # Zona
                zona = determinar_zona(titulo, local, cidade)
                if not zona:
                    for z in zonas_cidade:
                        if z.lower() in local.lower() or z.lower() in titulo.lower():
                            zona = z
                            break

                lat, lon = None, None
                if zona and zona in zonas_cidade:
                    zd = zonas_cidade[zona]
                    lat, lon = zd["lat"], zd["lon"]

                anuncios.append({
                    "titulo": titulo[:120],
                    "preco": preco,
                    "descricao": local,
                    "link": link,
                    "data": "",
                    "disponivel": disp,
                    "lat": lat,
                    "lon": lon,
                    "zona": zona,
                    "fonte": "HousingAnywhere",
                })
            except Exception:
                continue

        print(f"[HousingAnywhere] {cidade}: {len(anuncios)} anuncios")
        return anuncios

    except Exception as e:
        print(f"[HousingAnywhere] Erro {cidade}: {e}")
        return []


# =============================================================================
# WEB SCRAPING - SPOTAHOME (quartos verificados para estudantes)
# =============================================================================

def fetch_spotahome(cidade, max_anuncios=20):
    """Extrai anuncios do Spotahome - quartos verificados."""
    urls = {
        "Porto": "https://www.spotahome.com/s/porto--pt",
        "Lisboa": "https://www.spotahome.com/s/lisbon--pt",
        "Coimbra": "https://www.spotahome.com/s/coimbra--pt",
    }
    url = urls.get(cidade)
    if not url:
        return []

    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"),
        "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Spotahome usa links /for-rent:rooms/
        links = soup.find_all("a", href=re.compile(r"/for-rent:rooms/"))
        anuncios = []
        vistos = set()
        zonas_cidade = ZONAS.get(cidade, {})

        for a in links[:max_anuncios]:
            try:
                href = a.get("href", "")
                if href in vistos:
                    continue
                vistos.add(href)

                if href.startswith("/"):
                    link = "https://www.spotahome.com" + href
                else:
                    link = href

                txt = a.get_text(strip=True)
                if not txt or len(txt) < 10:
                    continue

                # Preco
                preco = None
                for padrao in [r'€\s*([\d\.]+)', r'([\d\.]+)\s*€']:
                    m = re.search(padrao, txt, re.IGNORECASE)
                    if m:
                        s = m.group(1).replace('.', '').replace(',', '.')
                        try:
                            preco = float(s)
                            break
                        except ValueError:
                            continue

                if not preco or preco < 100 or preco > 5000:
                    continue

                # Titulo - limpar texto
                titulo = txt[:150]

                # Disponibilidade
                disp = None
                m = re.search(r'Dispon[ií]vel\s+(\d+\s+\w+|agora|j[aá])', txt, re.IGNORECASE)
                if m:
                    disp = "Disponivel " + m.group(1)

                # Zona
                zona = determinar_zona(titulo, "", cidade)
                if not zona:
                    for z in zonas_cidade:
                        if z.lower() in titulo.lower():
                            zona = z
                            break

                lat, lon = None, None
                if zona and zona in zonas_cidade:
                    zd = zonas_cidade[zona]
                    lat, lon = zd["lat"], zd["lon"]

                anuncios.append({
                    "titulo": titulo[:120],
                    "preco": preco,
                    "descricao": f"Quarto verificado em {cidade}",
                    "link": link,
                    "data": "",
                    "disponivel": disp,
                    "lat": lat,
                    "lon": lon,
                    "zona": zona,
                    "fonte": "Spotahome",
                })
            except Exception:
                continue

        print(f"[Spotahome] {cidade}: {len(anuncios)} anuncios")
        return anuncios

    except Exception as e:
        print(f"[Spotahome] Erro {cidade}: {e}")
        return []


# =============================================================================
# TENTATIVA IDEALISTA / OLX (protegidos por anti-bot)
# ============================================================================= / OLX (protegidos por anti-bot)
# =============================================================================

def fetch_idealista_scraping(cidade):
    """Tentativa de scraping do Idealista. Nota: usa DataDome CAPTCHA."""
    print(f"[Idealista] Aviso: Idealista usa protecao DataDome. Tentativa pode falhar.")
    return []


def fetch_olx_scraping(cidade):
    """Tentativa de scraping do OLX. Nota: usa Cloudflare."""
    print(f"[OLX] Aviso: OLX usa protecao Cloudflare. Tentativa pode falhar.")
    return []


# =============================================================================
# DADOS DE DEMONSTRACAO (fallback final, por cidade)
# =============================================================================

def get_demo_data(cidade):
    demos = []
    zonas_cidade = ZONAS.get(cidade, {})
    if not zonas_cidade:
        return demos
    nomes_zonas = list(zonas_cidade.keys())

    if cidade == "Porto":
        titulos = [
            "Quarto espacoso junto ao Polo da Asprela",
            "Quarto mobilado na Boavista com transportes",
            "Quarto individual em apartamento partilhado - Cedofeita",
            "Quarto na Foz com vista para o mar",
            "Quarto economico proximo do Campanha",
        ]
        precos = [250, 300, 275, 400, 220]
    elif cidade == "Lisboa":
        titulos = [
            "Quarto junto ao IST Alameda",
            "Quarto em Alvalade proximo metro",
            "Quarto na Avenidas Novas com varanda",
            "Quarto economico Intendente",
            "Quarto em Belem mobilado",
        ]
        precos = [350, 400, 450, 280, 320]
    else:
        titulos = [
            "Quarto na Alta Universitaria",
            "Quarto mobilado junto a UC",
            "Quarto em Celas com transportes",
            "Quarto economico Santa Clara",
            "Quarto em apartamento partilhado - Baixa",
        ]
        precos = [200, 220, 180, 160, 190]

    for i in range(min(10, len(nomes_zonas))):
        zona = nomes_zonas[i % len(nomes_zonas)]
        zd = zonas_cidade[zona]
        demos.append({
            "titulo": titulos[i % len(titulos)],
            "preco": precos[i % len(precos)],
            "descricao": f"Excelente quarto para estudante em {zona}, {cidade}.",
            "link": "#",
            "data": datetime.now().strftime("%Y-%m-%d"),
            "disponivel": None,
            "lat": zd["lat"],
            "lon": zd["lon"],
            "zona": zona,
            "fonte": "Dados de demonstracao",
        })
    return demos


# =============================================================================
# CARREGAMENTO COMBINADO (multiplas fontes)
# =============================================================================

def carregar_anuncios(cidade):
    agora = time.time()
    cache = CACHE.get(cidade, {"anuncios": None, "timestamp": None, "fonte": None})
    if cache["anuncios"] and cache["timestamp"] and (agora - cache["timestamp"] < CACHE_TTL):
        return cache["anuncios"], cache["fonte"]

    print(f"[Cache] Atualizando dados para {cidade}...")
    fontes_dict = {}   # fonte_nome -> lista de anuncios
    fontes_ativas = []

    # Fonte 1: Imovirtual (mais confiavel)
    print(f"[Scraping] A tentar Imovirtual (ate {MAX_PAGES} paginas)...")
    imovirtual = fetch_imovirtual_todas_paginas(cidade)
    if imovirtual:
        fontes_dict["Imovirtual"] = imovirtual
        fontes_ativas.append(f"Imovirtual ({len(imovirtual)})")

    # Fonte 2: CustoJusto (via JSON Next.js)
    print(f"[Scraping] A tentar CustoJusto...")
    cj = fetch_custojusto_scraping(cidade, max_anuncios=40)
    if cj:
        fontes_dict["CustoJusto"] = cj
        fontes_ativas.append(f"CustoJusto ({len(cj)})")

    # Fonte 3: HousingAnywhere
    print(f"[Scraping] A tentar HousingAnywhere...")
    ha = fetch_housinganywhere(cidade, max_anuncios=20)
    if ha:
        fontes_dict["HousingAnywhere"] = ha
        fontes_ativas.append(f"HousingAnywhere ({len(ha)})")

    # Fonte 4: Spotahome
    print(f"[Scraping] A tentar Spotahome...")
    sp = fetch_spotahome(cidade, max_anuncios=20)
    if sp:
        fontes_dict["Spotahome"] = sp
        fontes_ativas.append(f"Spotahome ({len(sp)})")

    # Fallback para demo
    if not fontes_dict:
        print(f"[Fallback] Todas as fontes falharam. A usar dados de demonstracao.")
        fontes_dict["Demo"] = get_demo_data(cidade)
        fontes_ativas = ["Dados de demonstracao"]

    # Remove duplicados DENTRO de cada fonte
    for fonte_nome, lista in fontes_dict.items():
        vistos = set()
        unicos = []
        for a in lista:
            key = a.get("link", "") or a.get("titulo", "")
            if key and key not in vistos:
                vistos.add(key)
                unicos.append(a)
        fontes_dict[fonte_nome] = unicos

    # INTERLEAVE round-robin: misturar fontes 1-a-1 para nao ficar tudo de uma fonte junto
    todas_fontes = []
    nomes_fontes = list(fontes_dict.keys())
    indices = {nome: 0 for nome in nomes_fontes}

    while True:
        algum_adicionado = False
        for nome in nomes_fontes:
            lista = fontes_dict[nome]
            idx = indices[nome]
            if idx < len(lista):
                todas_fontes.append(lista[idx])
                indices[nome] = idx + 1
                algum_adicionado = True
        if not algum_adicionado:
            break

    fonte_str = " + ".join(fontes_ativas)
    CACHE[cidade] = {"anuncios": todas_fontes, "timestamp": agora, "fonte": fonte_str}
    print(f"[Cache] {cidade}: {len(todas_fontes)} anuncios unicos | Fontes: {fonte_str}")
    return todas_fontes, fonte_str


# =============================================================================
# FLASK APP
# =============================================================================

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UniCasa - Quartos para Estudantes</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        :root {
            --primary: #2c5282; --primary-light: #4299e1; --accent: #ed8936;
            --bg: #f7fafc; --card-bg: #ffffff; --text: #2d3748;
            --text-muted: #718096; --border: #e2e8f0;
        }
        * { box-sizing: border-box; }
        body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; line-height: 1.6; }
        .navbar {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
            padding: 1rem 0; box-shadow: 0 2px 15px rgba(44,82,130,0.25);
        }
        .navbar-brand { font-size: 1.6rem; font-weight: 700; color: #fff !important; }
        .navbar-brand span { color: var(--accent); }
        .stats-bar { background: #fff; border-bottom: 1px solid var(--border); padding: 0.75rem 0; }
        .filter-card {
            background: var(--card-bg); border-radius: 14px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.06); padding: 1.5rem; margin-bottom: 1.5rem;
        }
        .form-label { font-weight: 600; font-size: 0.875rem; color: var(--text-muted); }
        .form-select, .form-control {
            border: 2px solid var(--border); border-radius: 10px;
            padding: 0.625rem 1rem; font-size: 0.95rem; transition: all 0.2s;
        }
        .form-select:focus, .form-control:focus {
            border-color: var(--primary-light); box-shadow: 0 0 0 3px rgba(66,153,225,0.15);
        }
        .btn-primary {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
            border: none; border-radius: 10px; padding: 0.625rem 1.5rem;
            font-weight: 600; transition: transform 0.15s, box-shadow 0.15s;
        }
        .btn-primary:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(44,82,130,0.3); }
        .room-card {
            background: var(--card-bg); border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.06); border: 1px solid var(--border);
            overflow: hidden; transition: transform 0.2s, box-shadow 0.2s;
            height: 100%; display: flex; flex-direction: column;
        }
        .room-card:hover { transform: translateY(-4px); box-shadow: 0 12px 30px rgba(0,0,0,0.1); }
        .card-img-top { height: 180px; object-fit: cover; background: linear-gradient(135deg, #e2e8f0 0%, #cbd5e0 100%); }
        .card-body { padding: 1.25rem; flex: 1; display: flex; flex-direction: column; }
        .price-tag { font-size: 1.5rem; font-weight: 800; color: var(--primary); }
        .price-tag small { font-size: 0.85rem; font-weight: 500; color: var(--text-muted); }
        .badge-source { font-size: 0.7rem; font-weight: 600; padding: 0.35rem 0.65rem; border-radius: 20px; }
        .badge-imovirtual { background: #fef3c7; color: #92400e; }
        .badge-custojusto { background: #dbeafe; color: #1e40af; }
        .badge-housinganywhere { background: #d1fae5; color: #065f46; }
        .badge-spotahome { background: #fce7f3; color: #9d174d; }
        .badge-uniplaces { background: #dcfce7; color: #166534; }
        .badge-erasmusinn { background: #f3e8ff; color: #6b21a8; }
        .badge-demo { background: #f3e8ff; color: #6b21a8; }
        .badge-imovirtual { background: #fef3c7; color: #92400e; }
        .badge-custojusto { background: #dbeafe; color: #1e40af; }
        .badge-uniplaces { background: #dcfce7; color: #166534; }
        .badge-erasmusinn { background: #f3e8ff; color: #6b21a8; }
        .badge-demo { background: #f3e8ff; color: #6b21a8; }
        .distancia-box {
            background: linear-gradient(135deg, #ebf8ff 0%, #e6fffa 100%);
            border-radius: 10px; padding: 0.5rem 0.75rem; margin: 0.5rem 0;
            font-size: 0.875rem; font-weight: 600; color: var(--primary);
        }
        .distancia-box .numero { font-size: 1.1rem; }
        .zona-notas { margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px dashed var(--border); }
        .nota-item { display: flex; justify-content: space-between; align-items: center; font-size: 0.8rem; padding: 0.2rem 0; }
        .nota-label { color: var(--text-muted); }
        .nota-stars { letter-spacing: 1px; }
        .nota-boa { color: #38a169; }
        .nota-media { color: #d69e2e; }
        .nota-mau { color: #e53e3e; }
        .transp-box { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.25rem; margin-top: 0.5rem; font-size: 0.7rem; }
        .transp-item { text-align: center; padding: 0.25rem; border-radius: 6px; background: #f7fafc; }
        .transp-item .valor { font-weight: 700; color: var(--primary); }
        .btn-ver-anuncio {
            display: block; width: 100%;
            background: linear-gradient(135deg, var(--accent) 0%, #dd6b20 100%);
            color: #fff; border: none; border-radius: 10px; padding: 0.75rem;
            font-weight: 700; font-size: 0.95rem; text-decoration: none;
            text-align: center; margin-top: auto; transition: all 0.2s;
        }
        .btn-ver-anuncio:hover { color: #fff; transform: translateY(-2px); box-shadow: 0 6px 20px rgba(237,137,54,0.35); }
        .alert-info-custom { background: linear-gradient(135deg, #ebf8ff 0%, #e6fffa 100%); border: 1px solid #90cdf4; border-radius: 12px; color: #2c5282; }
        .alert-warning-custom { background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%); border: 1px solid #f6e05e; border-radius: 12px; color: #744210; }
        .empty-state { text-align: center; padding: 3rem 1rem; color: var(--text-muted); }
        .form-range { margin-top: 0.25rem; }
        .form-range + output { font-size: 0.8rem; margin-left: 0.5rem; vertical-align: middle; }
        .fonte-badge { font-size: 0.75rem; padding: 0.25rem 0.5rem; border-radius: 6px; margin-right: 0.5rem; }
        @media (max-width: 768px) {
            .filter-card .row > div { margin-bottom: 0.75rem; }
            .price-tag { font-size: 1.25rem; }
        }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="container">
            <a class="navbar-brand" href="/">Uni<span>Casa</span></a>
            <span style="color:rgba(255,255,255,0.8);font-size:0.9rem;">Busca Inteligente para Estudantes</span>
        </div>
    </nav>

    {% if fonte and 'demonstracao' in fonte.lower() %}
    <div class="alert-warning-custom py-2 text-center">
        <strong>Modo de Demonstracao ativo</strong> — Nao foi possivel carregar dados reais.
        <a href="/refresh?cidade={{ cidade_sel }}" class="text-decoration-underline">Tentar novamente</a>
    </div>
    {% elif fonte %}
    <div class="alert-info-custom py-2 text-center">
        <strong>Fontes ativas: {{ fonte }}</strong> —
        <a href="/refresh?cidade={{ cidade_sel }}" class="text-decoration-underline">Atualizar agora</a>
    </div>
    {% endif %}

    <div class="stats-bar">
        <div class="container d-flex justify-content-between align-items-center flex-wrap">
            <span><strong>{{ total }}</strong> anuncios em <strong>{{ cidade_sel }}</strong></span>
            <span class="text-muted" style="font-size:0.85rem;">Cache: 15 minutos | Atualizado: {{ agora }}</span>
        </div>
    </div>

    <div class="container py-4">
        <div class="filter-card">
            <form method="GET" action="/" class="row g-3 align-items-end">
                <!-- LINHA 1: Cidade + Faculdade -->
                <div class="col-md-6">
                    <label class="form-label">Cidade</label>
                    <select name="cidade" class="form-select" id="cidadeSelect" onchange="atualizarFaculdades()">
                        {% for c in cidades %}
                        <option value="{{ c }}" {% if cidade_sel == c %}selected{% endif %}>{{ c }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="col-md-6">
                    <label class="form-label">Faculdade (para calcular distancia)</label>
                    <select name="faculdade" class="form-select" id="faculdadeSelect">
                        <option value="">-- Escolher faculdade --</option>
                        {% for fac in faculdades %}
                        <option value="{{ fac }}" {% if faculdade_sel == fac %}selected{% endif %}>{{ fac }}</option>
                        {% endfor %}
                    </select>
                </div>

                <!-- LINHA 2: Preco Min, Preco Max, Dist Max, Ordenar -->
                <div class="col-md-3">
                    <label class="form-label">Preco Min (EUR)</label>
                    <input type="number" name="preco_min" class="form-control" placeholder="0"
                           value="{{ preco_min or '' }}">
                </div>
                <div class="col-md-3">
                    <label class="form-label">Preco Max (EUR)</label>
                    <input type="number" name="preco_max" class="form-control" placeholder="max"
                           value="{{ preco_max or '' }}">
                </div>
                <div class="col-md-3">
                    <label class="form-label">Dist. Max (km)</label>
                    <input type="number" name="dist_max" class="form-control" placeholder="km"
                           value="{{ dist_max or '' }}" step="0.1">
                </div>
                <div class="col-md-3">
                    <label class="form-label">Ordenar por</label>
                    <select name="ordenar" class="form-select">
                        <option value="" {% if ordenar == '' %}selected{% endif %}>Mais recentes</option>
                        <option value="preco_asc" {% if ordenar == 'preco_asc' %}selected{% endif %}>Preco: Baixo → Alto</option>
                        <option value="preco_desc" {% if ordenar == 'preco_desc' %}selected{% endif %}>Preco: Alto → Baixo</option>
                        <option value="distancia" {% if ordenar == 'distancia' %}selected{% endif %}>Distancia a faculdade</option>
                        <option value="seguranca" {% if ordenar == 'seguranca' %}selected{% endif %}>Seguranca (melhor)</option>
                        <option value="ruido_asc" {% if ordenar == 'ruido_asc' %}selected{% endif %}>Menos ruido</option>
                        <option value="comercio" {% if ordenar == 'comercio' %}selected{% endif %}>Mais comercio</option>
                    </select>
                </div>

                <!-- LINHA 3: Seguranca, Ruido, Comercio, Botao -->
                <div class="col-md-3">
                    <label class="form-label">Seguranca minima (0-10)</label>
                    <div class="d-flex align-items-center">
                        <input type="range" name="seg_min" class="form-range flex-grow-1" min="0" max="10" step="1"
                               value="{{ seg_min or '0' }}" oninput="this.nextElementSibling.value=this.value">
                        <output class="badge bg-primary ms-2">{{ seg_min or '0' }}</output>
                    </div>
                </div>
                <div class="col-md-3">
                    <label class="form-label">Ruido maximo (0-10)</label>
                    <div class="d-flex align-items-center">
                        <input type="range" name="ruido_max" class="form-range flex-grow-1" min="0" max="10" step="1"
                               value="{{ ruido_max or '10' }}" oninput="this.nextElementSibling.value=this.value">
                        <output class="badge bg-primary ms-2">{{ ruido_max or '10' }}</output>
                    </div>
                </div>
                <div class="col-md-3">
                    <label class="form-label">Comercio minimo (0-10)</label>
                    <div class="d-flex align-items-center">
                        <input type="range" name="com_min" class="form-range flex-grow-1" min="0" max="10" step="1"
                               value="{{ com_min or '0' }}" oninput="this.nextElementSibling.value=this.value">
                        <output class="badge bg-primary ms-2">{{ com_min or '0' }}</output>
                    </div>
                </div>
                <div class="col-md-3">
                    <button type="submit" class="btn btn-primary w-100" style="margin-top:1.5rem;">🔍 Filtrar</button>
                </div>
            </form>
        </div>

        {% if faculdade_sel %}
        <div class="alert alert-info" style="border-radius:12px;">
            <strong>Faculdade:</strong> {{ faculdade_sel }} ({{ cidade_sel }})
            <span class="text-muted">| Distancia em linha reta (Haversine)</span>
        </div>
        {% endif %}

        {% if anuncios %}
        <div class="row g-4">
            {% for a in anuncios %}
            <div class="col-12 col-md-6 col-lg-4">
                <div class="room-card">
                    {% if a.imagem %}
                    <img src="{{ a.imagem }}" class="card-img-top" alt="{{ a.titulo }}">
                    {% else %}
                    <div class="card-img-top d-flex align-items-center justify-content-center text-muted">
                        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"></path>
                            <polyline points="9 22 9 12 15 12 15 22"></polyline>
                        </svg>
                    </div>
                    {% endif %}
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            {% set fonte_key = a.fonte.lower().replace(' ', '').replace('.', '') if a.fonte else 'demo' %}
                            <span class="badge badge-{{ fonte_key }}">
                                {{ a.fonte or 'Desconhecida' }}
                            </span>
                            <span class="text-muted" style="font-size:0.75rem;">{{ a.data or '' }}</span>
                        </div>
                        <h5 class="card-title" style="font-size:1rem;font-weight:700;line-height:1.4;">{{ a.titulo or 'Sem titulo' }}</h5>
                        <div class="price-tag">{{ "%.0f"|format(a.preco) }} <small>EUR/mes</small></div>
                        {% if a.disponivel %}
                        <div class="mt-1" style="font-size:0.8rem;">
                            <span class="badge bg-success">{{ a.disponivel }}</span>
                        </div>
                        {% endif %}
                        {% if a.zona %}
                        <span class="badge bg-light text-dark border" style="font-size:0.75rem;">{{ a.zona }}</span>
                        {% endif %}
                        {% if a.distancia is not none %}
                        <div class="distancia-box">
                            Distancia a <strong>{{ faculdade_sel }}</strong>:
                            <span class="numero">{{ a.distancia }} km</span>
                        </div>
                        {% endif %}
                        <p class="card-text text-muted" style="font-size:0.85rem;margin-top:0.5rem;">
                            {{ a.descricao[:140] }}{% if a.descricao|length > 140 %}...{% endif %}
                        </p>
                        {% if a.zona and a.zona in zonas %}
                        <div class="zona-notas">
                            {% set zn = zonas[a.zona] %}
                            <div class="nota-item"><span class="nota-label">Seguranca</span>
                                <span class="nota-stars {{ badge_nota(zn.seguranca) }}">{{ estrelas_html(zn.seguranca) }}</span></div>
                            <div class="nota-item"><span class="nota-label">Ruido</span>
                                <span class="nota-stars {{ badge_nota(zn.ruido) }}">{{ estrelas_html(zn.ruido) }}</span></div>
                            <div class="nota-item"><span class="nota-label">Comercio</span>
                                <span class="nota-stars {{ badge_nota(zn.comercio) }}">{{ estrelas_html(zn.comercio) }}</span></div>
                            <div class="transp-box">
                                <div class="transp-item"><div>Metro</div><div class="valor">{{ zn.metro_min }}m</div></div>
                                <div class="transp-item"><div>Bus</div><div class="valor">{{ zn.bus_min }}m</div></div>
                                <div class="transp-item"><div>Comboio</div><div class="valor">{{ zn.comboio_min }}m</div></div>
                            </div>
                        </div>
                        {% endif %}
                        {% if a.link and a.link != '#' %}
                        <a href="{{ a.link }}" target="_blank" rel="noopener" class="btn-ver-anuncio mt-3">🔗 Ver Anuncio Original</a>
                        {% endif %}
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="empty-state">
            <h4>Nenhum anuncio encontrado</h4>
            <p>Tenta ajustar os filtros ou <a href="/refresh?cidade={{ cidade_sel }}">atualizar os dados</a>.</p>
        </div>
        {% endif %}
    </div>

    <footer class="text-center py-4 text-muted" style="border-top:1px solid var(--border);margin-top:2rem;">
        <small>UniCasa — Busca Inteligente para Estudantes — Porto | Lisboa | Coimbra</small>
    </footer>

    <script>
    const faculdadesPorCidade = {{ faculdades_json | safe }};
    const faculdadeSelecionadaAtual = "{{ faculdade_sel }}";
    
    function atualizarFaculdades() {
        const cidade = document.getElementById('cidadeSelect').value;
        const facSelect = document.getElementById('faculdadeSelect');
        facSelect.innerHTML = '<option value="">-- Escolher faculdade --</option>';
        if (faculdadesPorCidade[cidade]) {
            faculdadesPorCidade[cidade].forEach(fac => {
                const opt = document.createElement('option');
                opt.value = fac;
                opt.textContent = fac;
                if (fac === faculdadeSelecionadaAtual) {
                    opt.selected = true;
                }
                facSelect.appendChild(opt);
            });
        }
    }
    // Inicializar na pagina
    document.addEventListener('DOMContentLoaded', function() {
        atualizarFaculdades();
    });
    </script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

@app.route("/")
def index():
    cidade_sel = request.args.get("cidade", "Porto").strip()
    if cidade_sel not in CIDADES:
        cidade_sel = "Porto"

    faculdade_sel = request.args.get("faculdade", "").strip()
    preco_min = request.args.get("preco_min", "", type=str)
    preco_max = request.args.get("preco_max", "", type=str)
    ordenar = request.args.get("ordenar", "")
    seg_min = request.args.get("seg_min", "", type=str)
    ruido_max = request.args.get("ruido_max", "", type=str)
    com_min = request.args.get("com_min", "", type=str)
    dist_max = request.args.get("dist_max", "", type=str)

    pmin = float(preco_min) if preco_min else None
    pmax = float(preco_max) if preco_max else None
    seg_min_v = int(seg_min) if seg_min else None
    ruido_max_v = int(ruido_max) if ruido_max else None
    com_min_v = int(com_min) if com_min else None
    dist_max_v = float(dist_max) if dist_max else None

    anuncios, fonte = carregar_anuncios(cidade_sel)
    facs_cidade = list(CIDADES[cidade_sel].keys())

    if faculdade_sel and faculdade_sel in CIDADES[cidade_sel]:
        f = CIDADES[cidade_sel][faculdade_sel]
        for a in anuncios:
            lat = a.get("lat")
            lon = a.get("lon")
            if lat and lon:
                a["distancia"] = round(haversine(lat, lon, f["lat"], f["lon"]), 1)
            else:
                a["distancia"] = None
    else:
        for a in anuncios:
            a["distancia"] = None

    zonas_cidade = ZONAS.get(cidade_sel, {})
    filtrados = []
    for a in anuncios:
        preco = a.get("preco")
        if preco is None:
            continue
        if pmin is not None and preco < pmin:
            continue
        if pmax is not None and preco > pmax:
            continue

        zona = a.get("zona")
        if zona and zona in zonas_cidade:
            zd = zonas_cidade[zona]
            if seg_min_v is not None and zd["seguranca"] < seg_min_v:
                continue
            if ruido_max_v is not None and zd["ruido"] > ruido_max_v:
                continue
            if com_min_v is not None and zd["comercio"] < com_min_v:
                continue

        dist = a.get("distancia")
        if dist_max_v is not None:
            if dist is None or dist > dist_max_v:
                continue

        filtrados.append(a)

    if ordenar == "preco_asc":
        filtrados.sort(key=lambda x: x.get("preco", float("inf")))
    elif ordenar == "preco_desc":
        filtrados.sort(key=lambda x: x.get("preco", 0), reverse=True)
    elif ordenar == "distancia":
        filtrados.sort(key=lambda x: x.get("distancia") if x.get("distancia") is not None else float("inf"))
    elif ordenar == "seguranca":
        filtrados.sort(key=lambda x: zonas_cidade.get(x.get("zona"), {}).get("seguranca", 0), reverse=True)
    elif ordenar == "ruido_asc":
        filtrados.sort(key=lambda x: zonas_cidade.get(x.get("zona"), {}).get("ruido", 10))
    elif ordenar == "comercio":
        filtrados.sort(key=lambda x: zonas_cidade.get(x.get("zona"), {}).get("comercio", 0), reverse=True)

    return render_template_string(
        HTML_TEMPLATE,
        anuncios=filtrados,
        total=len(filtrados),
        fonte=fonte,
        cidades=NOMES_CIDADES,
        cidade_sel=cidade_sel,
        faculdades=facs_cidade,
        faculdade_sel=faculdade_sel,
        faculdades_json=json.dumps({c: list(v.keys()) for c, v in CIDADES.items()}),
        preco_min=preco_min,
        preco_max=preco_max,
        seg_min=seg_min,
        ruido_max=ruido_max,
        com_min=com_min,
        dist_max=dist_max,
        ordenar=ordenar,
        zonas=zonas_cidade,
        agora=datetime.now().strftime("%H:%M"),
        estrelas_html=estrelas_html,
        badge_nota=badge_nota,
    )


@app.route("/refresh")
def refresh():
    cidade = request.args.get("cidade", "Porto")
    if cidade in CACHE:
        CACHE[cidade] = {"anuncios": None, "timestamp": None, "fonte": None}
    return f"""<script>window.location.href='/?cidade={cidade}';</script>"""


@app.route("/api/anuncios")
def api_anuncios():
    cidade = request.args.get("cidade", "Porto")
    if cidade not in CIDADES:
        return jsonify({"erro": "Cidade invalida"}), 400
    anuncios, fonte = carregar_anuncios(cidade)
    return jsonify({"cidade": cidade, "fonte": fonte, "total": len(anuncios), "anuncios": anuncios})


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    print("=" * 60)
    print("  UniCasa - Agregador de Quartos para Estudantes")
    print("  Cidades: Porto | Lisboa | Coimbra")
    print("=" * 60)
    print(f"  Faculdades: {sum(len(v) for v in CIDADES.values())} (total)")
    print(f"  Zonas: {sum(len(v) for v in ZONAS.values())} (total)")
    print(f"  Fontes: Imovirtual, CustoJusto, HousingAnywhere, Spotahome (Idealista/OLX bloqueados)")
    print(f"  URL: http://0.0.0.0:{port}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=False)
