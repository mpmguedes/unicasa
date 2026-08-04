# -*- coding: utf-8 -*-
"""
Aloja-Te — Encontra quarto sem complicações
Agregador de anúncios de quartos para estudantes em Portugal (Flask, single-file).

Fontes ativas:
  * Imovirtual  — scraping HTML (principal)
  * OLX         — scraping HTML
  * CustoJusto  — JSON embutido do Next.js (__NEXT_DATA__)
  * Idealista   — via Playwright (Chromium completo, ultrapassa o DataDome)

Desativadas:
  * HousingAnywhere / Spotahome — renderizam em JavaScript, requerem Camoufox

Se nenhuma fonte retornar resultados, a página mostra o estado vazio com
mensagem para tentar novamente (sem dados fictícios).
"""

import json
import math
import os
import re
import time
import unicodedata
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, redirect, render_template_string, request, url_for

# ---------------------------------------------------------------------------
# Configuração / otimizações para Render (512MB RAM)
# ---------------------------------------------------------------------------
PORT = int(os.environ.get("PORT", 5000))
CACHE_TTL = 30 * 60          # 30 minutos
MAX_PAGES = 2                # Imovirtual
MAX_ARTICLES_PER_PAGE = 25   # artigos por página
MAX_TOTAL = 200              # limite de anúncios apresentados
REQUEST_TIMEOUT = 8          # segundos
MAX_CUSTOJUSTO = 30          # anúncios do CustoJusto
GEOCODE_NOMINATIM = os.environ.get("GEOCODE_NOMINATIM", "0") == "1"
# Idealista é bloqueado por DataDome (CAPTCHA/JS) para pedidos simples; o scraper
# usa Playwright com Chromium completo (channel="chromium") para ultrapassar o
# challenge. Ativar/desativar com ENABLE_IDEALISTA (default: ativo).
#   pip install playwright  +  playwright install chromium
ENABLE_IDEALISTA = os.environ.get("ENABLE_IDEALISTA", "1") == "1"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/124.0.0.0 Safari/537.36"),
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
}

# ---------------------------------------------------------------------------
# Cidades e Faculdades
# ---------------------------------------------------------------------------
CIDADES = ["Porto", "Lisboa", "Coimbra"]
CIDADES_EXTRA = ["Algarve", "Aveiro", "Braga", "Évora", "Vila Real"]
CIDADES_TODAS = CIDADES + CIDADES_EXTRA

CIDADE_SLUG = {"porto": "Porto", "lisboa": "Lisboa", "coimbra": "Coimbra",
               "vila real": "Vila Real", "aveiro": "Aveiro", "braga": "Braga",
               "evora": "Évora", "algarve": "Algarve", "faro": "Algarve"}

CIDADE_CENTRO = {
    "Porto": (41.1579, -8.6291),
    "Lisboa": (38.7223, -9.1393),
    "Coimbra": (40.2033, -8.4103),
    "Vila Real": (41.3008, -7.7441),
    "Aveiro": (40.6405, -8.6538),
    "Braga": (41.5454, -8.4265),
    "Évora": (38.5714, -7.9046),
    "Algarve": (37.0194, -7.9304),
}

FACULDADES = {
    "Porto": [
        {"nome": "FEUP", "lat": 41.1785, "lon": -8.5950},
        {"nome": "FEP", "lat": 41.1620, "lon": -8.6260},
        {"nome": "FBAUP", "lat": 41.1494, "lon": -8.6130},
        {"nome": "FAUP", "lat": 41.1470, "lon": -8.6140},
        {"nome": "FLUP", "lat": 41.1610, "lon": -8.6000},
        {"nome": "ISEP", "lat": 41.1810, "lon": -8.6040},
        {"nome": "ESMAE", "lat": 41.1480, "lon": -8.6100},
        {"nome": "Catolica Porto", "lat": 41.1550, "lon": -8.6290},
        {"nome": "FMUP", "lat": 41.1458, "lon": -8.6170},
        {"nome": "FCUP", "lat": 41.1462, "lon": -8.6165},
        {"nome": "FDUP", "lat": 41.1455, "lon": -8.6155},
        {"nome": "FPCEUP", "lat": 41.1468, "lon": -8.6145},
        {"nome": "FADEUP", "lat": 41.1835, "lon": -8.5920},
        {"nome": "ICBAS", "lat": 41.1450, "lon": -8.6180},
        {"nome": "ESE", "lat": 41.1600, "lon": -8.6050},
        {"nome": "ESTSP", "lat": 41.1555, "lon": -8.6120},
        {"nome": "ISCAP", "lat": 41.1590, "lon": -8.6080},
    ],
    "Lisboa": [
        {"nome": "IST Alameda", "lat": 38.7368, "lon": -9.1393},
        {"nome": "IST Taguspark", "lat": 38.7370, "lon": -9.3030},
        {"nome": "FCUL", "lat": 38.7560, "lon": -9.1580},
        {"nome": "FFLUL", "lat": 38.7520, "lon": -9.1580},
        {"nome": "FBAUL", "lat": 38.7070, "lon": -9.1450},
        {"nome": "FMUL", "lat": 38.7480, "lon": -9.1590},
        {"nome": "FDUL", "lat": 38.7525, "lon": -9.1575},
        {"nome": "ISEG", "lat": 38.7065, "lon": -9.1525},
        {"nome": "ISCTE-IUL", "lat": 38.7480, "lon": -9.1535},
        {"nome": "FCSH", "lat": 38.7570, "lon": -9.1530},
        {"nome": "NOVA SBE", "lat": 38.7320, "lon": -9.1490},
        {"nome": "ISA", "lat": 38.7260, "lon": -9.1830},
        {"nome": "FMD", "lat": 38.7485, "lon": -9.1585},
        {"nome": "FARMACIA ULisboa", "lat": 38.7565, "lon": -9.1575},
        {"nome": "ESAD.CR", "lat": 38.7100, "lon": -9.1400},
        {"nome": "Lusofona", "lat": 38.7200, "lon": -9.1450},
    ],
    "Coimbra": [
        {"nome": "UC Letras", "lat": 40.2090, "lon": -8.4240},
        {"nome": "UC Direito", "lat": 40.2070, "lon": -8.4250},
        {"nome": "UC Medicina", "lat": 40.2150, "lon": -8.4100},
        {"nome": "FCTUC", "lat": 40.1860, "lon": -8.4150},
        {"nome": "FEUC", "lat": 40.2050, "lon": -8.4200},
        {"nome": "FPCE", "lat": 40.2100, "lon": -8.4220},
        {"nome": "FCDE", "lat": 40.2080, "lon": -8.4180},
        {"nome": "FLUC", "lat": 40.2110, "lon": -8.4230},
        {"nome": "IPC", "lat": 40.2030, "lon": -8.4180},
        {"nome": "ESAC", "lat": 40.1980, "lon": -8.4250},
        {"nome": "ISCAC", "lat": 40.2120, "lon": -8.4200},
        {"nome": "ESTESC", "lat": 40.2000, "lon": -8.4150},
    ],
    "Vila Real": [
        {"nome": "UTAD — Campus Principal", "lat": 41.2837, "lon": -7.7339},
        {"nome": "UTAD — Polo Desportivo", "lat": 41.2865, "lon": -7.7300},
    ],
    "Aveiro": [
        {"nome": "UA — Campus de Santiago", "lat": 40.6299, "lon": -8.6572},
        {"nome": "ISCA-UA — Contabilidade", "lat": 40.6400, "lon": -8.6480},
    ],
    "Braga": [
        {"nome": "UMinho — Campus de Gualtar", "lat": 41.5588, "lon": -8.4010},
        {"nome": "UMinho — Centro (Congregados)", "lat": 41.5507, "lon": -8.4218},
    ],
    "Évora": [
        {"nome": "UÉ — Colégio do Espírito Santo", "lat": 38.5714, "lon": -7.9145},
        {"nome": "UÉ — Pólo da Mitra", "lat": 38.5328, "lon": -7.9195},
    ],
    "Algarve": [
        {"nome": "UAlg — Campus de Gambelas", "lat": 37.0557, "lon": -7.9761},
        {"nome": "UAlg — Campus da Penha", "lat": 37.0303, "lon": -7.9398},
    ],
}

# Ordem do dropdown de universidades: Porto, Lisboa, Coimbra, depois as restantes
# por ordem alfabética.
ORDEM_EXTRA = CIDADES_EXTRA
UNIVERSIDADES_GRUPOS = [{"cidade": c, "faculdades": FACULDADES.get(c, [])}
                        for c in CIDADES + ORDEM_EXTRA]
UNIVERSIDADES = [{"nome": f["nome"], "cidade": g["cidade"],
                  "lat": f["lat"], "lon": f["lon"]}
                 for g in UNIVERSIDADES_GRUPOS for f in g["faculdades"]]

# ---------------------------------------------------------------------------
# Zonas / freguesias com classificações
#   seguranca (0-10), ruido (0-10, maior=mais barulhento), comercio (0-10),
#   metro_min / bus_min / comboio_min (min a pé), lat, lon, aliases (keywords)
# ---------------------------------------------------------------------------
ZONAS = {
    "Porto": [
        {"nome": "Paranhos", "seguranca": 8, "ruido": 5, "comercio": 7,
         "metro_min": 5, "bus_min": 3, "comboio_min": 20, "lat": 41.1792, "lon": -8.6170,
         "aliases": ["paranhos", "asprela", "polo universita", "hospital sao joao", "sao joao"]},
        {"nome": "Cedofeita", "seguranca": 6, "ruido": 8, "comercio": 9,
         "metro_min": 5, "bus_min": 3, "comboio_min": 15, "lat": 41.1545, "lon": -8.6230,
         "aliases": ["cedofeita", "miguel bombarda"]},
        {"nome": "Bonfim", "seguranca": 5, "ruido": 7, "comercio": 7,
         "metro_min": 10, "bus_min": 5, "comboio_min": 12, "lat": 41.1490, "lon": -8.5980,
         "aliases": ["bonfim"]},
        {"nome": "Ramalde", "seguranca": 8, "ruido": 4, "comercio": 6,
         "metro_min": 15, "bus_min": 6, "comboio_min": 25, "lat": 41.1680, "lon": -8.6450,
         "aliases": ["ramalde"]},
        {"nome": "Aldoar", "seguranca": 8, "ruido": 3, "comercio": 5,
         "metro_min": 20, "bus_min": 8, "comboio_min": 30, "lat": 41.1700, "lon": -8.6600,
         "aliases": ["aldoar"]},
        {"nome": "Massarelos", "seguranca": 7, "ruido": 5, "comercio": 7,
         "metro_min": 12, "bus_min": 5, "comboio_min": 20, "lat": 41.1540, "lon": -8.6320,
         "aliases": ["massarelos"]},
        {"nome": "Miragaia", "seguranca": 6, "ruido": 6, "comercio": 6,
         "metro_min": 10, "bus_min": 5, "comboio_min": 18, "lat": 41.1430, "lon": -8.6250,
         "aliases": ["miragaia", "ribeira"]},
        {"nome": "Foz do Douro", "seguranca": 9, "ruido": 2, "comercio": 5,
         "metro_min": 25, "bus_min": 10, "comboio_min": 35, "lat": 41.1500, "lon": -8.6750,
         "aliases": ["foz do douro", "foz"]},
        {"nome": "Campanhã", "seguranca": 5, "ruido": 6, "comercio": 6,
         "metro_min": 12, "bus_min": 6, "comboio_min": 5, "lat": 41.1510, "lon": -8.5730,
         "aliases": ["campanha", "estacao campanha"]},
        {"nome": "Boavista", "seguranca": 7, "ruido": 6, "comercio": 9,
         "metro_min": 6, "bus_min": 3, "comboio_min": 15, "lat": 41.1590, "lon": -8.6280,
         "aliases": ["boavista"]},
        {"nome": "Lordelo do Ouro", "seguranca": 7, "ruido": 5, "comercio": 7,
         "metro_min": 10, "bus_min": 4, "comboio_min": 18, "lat": 41.1580, "lon": -8.6530,
         "aliases": ["lordelo"]},
        {"nome": "Antas", "seguranca": 7, "ruido": 6, "comercio": 8,
         "metro_min": 4, "bus_min": 3, "comboio_min": 20, "lat": 41.1710, "lon": -8.5900,
         "aliases": ["antas", "dragao"]},
        {"nome": "Matosinhos Centro", "seguranca": 7, "ruido": 7, "comercio": 9,
         "metro_min": 8, "bus_min": 4, "comboio_min": 15, "lat": 41.1800, "lon": -8.6880,
         "aliases": ["matosinhos", "leixoes"]},
        {"nome": "Maia Centro", "seguranca": 8, "ruido": 4, "comercio": 7,
         "metro_min": 15, "bus_min": 8, "comboio_min": 10, "lat": 41.2350, "lon": -8.6200,
         "aliases": ["maia"]},
        {"nome": "Gondomar", "seguranca": 8, "ruido": 3, "comercio": 6,
         "metro_min": 20, "bus_min": 10, "comboio_min": 15, "lat": 41.1430, "lon": -8.5330,
         "aliases": ["gondomar"]},
        {"nome": "Vila Nova de Gaia Centro", "seguranca": 7, "ruido": 6, "comercio": 8,
         "metro_min": 10, "bus_min": 5, "comboio_min": 8, "lat": 41.1330, "lon": -8.6100,
         "aliases": ["vila nova de gaia", "gaia", "afurada", "santa marinha"]},
    ],
    "Lisboa": [
        {"nome": "Alameda", "seguranca": 7, "ruido": 7, "comercio": 8,
         "metro_min": 3, "bus_min": 2, "comboio_min": 15, "lat": 38.7370, "lon": -9.1330,
         "aliases": ["alameda"]},
        {"nome": "Avenidas Novas", "seguranca": 8, "ruido": 5, "comercio": 9,
         "metro_min": 5, "bus_min": 2, "comboio_min": 12, "lat": 38.7390, "lon": -9.1480,
         "aliases": ["avenidas novas", "campo pequeno"]},
        {"nome": "Saldanha", "seguranca": 7, "ruido": 8, "comercio": 10,
         "metro_min": 2, "bus_min": 2, "comboio_min": 8, "lat": 38.7350, "lon": -9.1450,
         "aliases": ["saldanha"]},
        {"nome": "Arroios", "seguranca": 6, "ruido": 7, "comercio": 9,
         "metro_min": 4, "bus_min": 3, "comboio_min": 10, "lat": 38.7330, "lon": -9.1360,
         "aliases": ["arroios"]},
        {"nome": "Intendente", "seguranca": 5, "ruido": 8, "comercio": 8,
         "metro_min": 4, "bus_min": 3, "comboio_min": 12, "lat": 38.7210, "lon": -9.1390,
         "aliases": ["intendente"]},
        {"nome": "Graça", "seguranca": 6, "ruido": 5, "comercio": 6,
         "metro_min": 10, "bus_min": 5, "comboio_min": 20, "lat": 38.7160, "lon": -9.1340,
         "aliases": ["graca"]},
        {"nome": "Penha de França", "seguranca": 6, "ruido": 6, "comercio": 7,
         "metro_min": 8, "bus_min": 4, "comboio_min": 15, "lat": 38.7200, "lon": -9.1270,
         "aliases": ["penha de franca", "penha"]},
        {"nome": "Belém", "seguranca": 9, "ruido": 3, "comercio": 6,
         "metro_min": 25, "bus_min": 8, "comboio_min": 15, "lat": 38.6980, "lon": -9.2020,
         "aliases": ["belem"]},
        {"nome": "Campo Grande", "seguranca": 7, "ruido": 6, "comercio": 8,
         "metro_min": 5, "bus_min": 3, "comboio_min": 10, "lat": 38.7590, "lon": -9.1550,
         "aliases": ["campo grande"]},
        {"nome": "Benfica", "seguranca": 8, "ruido": 4, "comercio": 7,
         "metro_min": 15, "bus_min": 6, "comboio_min": 12, "lat": 38.7510, "lon": -9.2030,
         "aliases": ["benfica"]},
        {"nome": "Chelas", "seguranca": 5, "ruido": 6, "comercio": 6,
         "metro_min": 12, "bus_min": 5, "comboio_min": 20, "lat": 38.7570, "lon": -9.1110,
         "aliases": ["chelas"]},
        {"nome": "Alvalade", "seguranca": 8, "ruido": 5, "comercio": 9,
         "metro_min": 6, "bus_min": 3, "comboio_min": 15, "lat": 38.7540, "lon": -9.1440,
         "aliases": ["alvalade"]},
        {"nome": "Parque das Nações", "seguranca": 9, "ruido": 4, "comercio": 8,
         "metro_min": 10, "bus_min": 5, "comboio_min": 5, "lat": 38.7670, "lon": -9.0940,
         "aliases": ["parque das nacoes", "oriente", "expo"]},
        {"nome": "Estrela", "seguranca": 8, "ruido": 4, "comercio": 7,
         "metro_min": 12, "bus_min": 5, "comboio_min": 18, "lat": 38.7080, "lon": -9.1630,
         "aliases": ["estrela"]},
        {"nome": "Santos", "seguranca": 7, "ruido": 6, "comercio": 8,
         "metro_min": 10, "bus_min": 4, "comboio_min": 12, "lat": 38.7070, "lon": -9.1560,
         "aliases": ["santos"]},
        {"nome": "Lapa", "seguranca": 8, "ruido": 4, "comercio": 7,
         "metro_min": 12, "bus_min": 5, "comboio_min": 15, "lat": 38.7060, "lon": -9.1660,
         "aliases": ["lapa"]},
        {"nome": "Anjos", "seguranca": 6, "ruido": 7, "comercio": 9,
         "metro_min": 4, "bus_min": 3, "comboio_min": 12, "lat": 38.7260, "lon": -9.1360,
         "aliases": ["anjos"]},
    ],
    "Coimbra": [
        {"nome": "Alta Universitária", "seguranca": 8, "ruido": 4, "comercio": 7,
         "metro_min": None, "bus_min": 2, "comboio_min": 20, "lat": 40.2070, "lon": -8.4240,
         "aliases": ["alta universita", "alta"]},
        {"nome": "Baixa", "seguranca": 6, "ruido": 7, "comercio": 9,
         "metro_min": None, "bus_min": 3, "comboio_min": 15, "lat": 40.2080, "lon": -8.4290,
         "aliases": ["baixa de coimbra", "baixa"]},
        {"nome": "Celas", "seguranca": 7, "ruido": 5, "comercio": 8,
         "metro_min": None, "bus_min": 5, "comboio_min": 18, "lat": 40.2140, "lon": -8.4120,
         "aliases": ["celas", "hospitais da universidade", "huc", "ipo"]},
        {"nome": "Santa Clara", "seguranca": 8, "ruido": 4, "comercio": 6,
         "metro_min": None, "bus_min": 10, "comboio_min": 25, "lat": 40.1950, "lon": -8.4420,
         "aliases": ["santa clara"]},
        {"nome": "Solum", "seguranca": 7, "ruido": 6, "comercio": 8,
         "metro_min": None, "bus_min": 4, "comboio_min": 15, "lat": 40.2140, "lon": -8.4080,
         "aliases": ["solum"]},
        {"nome": "Tovim", "seguranca": 6, "ruido": 5, "comercio": 6,
         "metro_min": None, "bus_min": 8, "comboio_min": 20, "lat": 40.2160, "lon": -8.4050,
         "aliases": ["tovim", "chao do bispo"]},
        {"nome": "Botânica", "seguranca": 7, "ruido": 5, "comercio": 7,
         "metro_min": None, "bus_min": 6, "comboio_min": 18, "lat": 40.2070, "lon": -8.4170,
         "aliases": ["botanica", "jardim botanico"]},
        {"nome": "S. Martinho", "seguranca": 7, "ruido": 4, "comercio": 7,
         "metro_min": None, "bus_min": 7, "comboio_min": 20, "lat": 40.2040, "lon": -8.4270,
         "aliases": ["martinho", "sao martinho"]},
        {"nome": "Portela", "seguranca": 6, "ruido": 6, "comercio": 7,
         "metro_min": None, "bus_min": 6, "comboio_min": 18, "lat": 40.2100, "lon": -8.4000,
         "aliases": ["portela"]},
        {"nome": "Lousã", "seguranca": 8, "ruido": 2, "comercio": 5,
         "metro_min": None, "bus_min": 30, "comboio_min": 25, "lat": 40.1130, "lon": -8.2470,
         "aliases": ["lousa"]},
    ],
    # Cidades sem metro: transportes por autocarro (e comboio onde existir estação).
    "Vila Real": [
        {"nome": "Centro", "seguranca": 7, "ruido": 6, "comercio": 9,
         "metro_min": None, "bus_min": 4, "comboio_min": None, "lat": 41.3000, "lon": -7.7440,
         "aliases": ["centro", "baixa"]},
        {"nome": "São Pedro", "seguranca": 7, "ruido": 5, "comercio": 7,
         "metro_min": None, "bus_min": 5, "comboio_min": None, "lat": 41.3040, "lon": -7.7400,
         "aliases": ["sao pedro"]},
        {"nome": "Mateus", "seguranca": 8, "ruido": 4, "comercio": 6,
         "metro_min": None, "bus_min": 8, "comboio_min": None, "lat": 41.2950, "lon": -7.7150,
         "aliases": ["mateus", "solar de mateus"]},
        {"nome": "Folhadela", "seguranca": 8, "ruido": 3, "comercio": 5,
         "metro_min": None, "bus_min": 6, "comboio_min": None, "lat": 41.2760, "lon": -7.7280,
         "aliases": ["folhadela"]},
        {"nome": "Lordelo", "seguranca": 7, "ruido": 5, "comercio": 7,
         "metro_min": None, "bus_min": 5, "comboio_min": None, "lat": 41.2950, "lon": -7.7600,
         "aliases": ["lordelo"]},
        {"nome": "Parada de Cunhos", "seguranca": 8, "ruido": 3, "comercio": 5,
         "metro_min": None, "bus_min": 10, "comboio_min": None, "lat": 41.2920, "lon": -7.7260,
         "aliases": ["parada de cunhos"]},
        {"nome": "Vila Marim", "seguranca": 8, "ruido": 3, "comercio": 5,
         "metro_min": None, "bus_min": 12, "comboio_min": None, "lat": 41.2770, "lon": -7.7560,
         "aliases": ["vila marim"]},
        {"nome": "Abambres", "seguranca": 8, "ruido": 3, "comercio": 4,
         "metro_min": None, "bus_min": 12, "comboio_min": None, "lat": 41.3150, "lon": -7.7600,
         "aliases": ["abambres"]},
    ],
    "Aveiro": [
        {"nome": "Centro", "seguranca": 7, "ruido": 6, "comercio": 9,
         "metro_min": None, "bus_min": 3, "comboio_min": 10, "lat": 40.6400, "lon": -8.6540,
         "aliases": ["centro", "baixa"]},
        {"nome": "Santiago", "seguranca": 8, "ruido": 4, "comercio": 7,
         "metro_min": None, "bus_min": 5, "comboio_min": 12, "lat": 40.6299, "lon": -8.6572,
         "aliases": ["santiago", "campus"]},
        {"nome": "Esgueira", "seguranca": 7, "ruido": 5, "comercio": 7,
         "metro_min": None, "bus_min": 5, "comboio_min": 15, "lat": 40.6520, "lon": -8.6280,
         "aliases": ["esgueira"]},
        {"nome": "Glória", "seguranca": 7, "ruido": 6, "comercio": 8,
         "metro_min": None, "bus_min": 4, "comboio_min": 10, "lat": 40.6405, "lon": -8.6450,
         "aliases": ["gloria"]},
        {"nome": "Vera Cruz", "seguranca": 6, "ruido": 7, "comercio": 9,
         "metro_min": None, "bus_min": 3, "comboio_min": 8, "lat": 40.6440, "lon": -8.6530,
         "aliases": ["vera cruz"]},
        {"nome": "Aradas", "seguranca": 7, "ruido": 5, "comercio": 7,
         "metro_min": None, "bus_min": 6, "comboio_min": 12, "lat": 40.6160, "lon": -8.6480,
         "aliases": ["aradas"]},
        {"nome": "São Bernardo", "seguranca": 7, "ruido": 4, "comercio": 6,
         "metro_min": None, "bus_min": 8, "comboio_min": 15, "lat": 40.6260, "lon": -8.6250,
         "aliases": ["sao bernardo"]},
        {"nome": "Santa Joana", "seguranca": 7, "ruido": 5, "comercio": 8,
         "metro_min": None, "bus_min": 5, "comboio_min": 10, "lat": 40.6310, "lon": -8.6400,
         "aliases": ["santa joana"]},
        {"nome": "Oliveirinha", "seguranca": 8, "ruido": 3, "comercio": 5,
         "metro_min": None, "bus_min": 10, "comboio_min": 15, "lat": 40.6070, "lon": -8.5900,
         "aliases": ["oliveirinha"]},
        {"nome": "Cacia", "seguranca": 8, "ruido": 3, "comercio": 6,
         "metro_min": None, "bus_min": 10, "comboio_min": 12, "lat": 40.6780, "lon": -8.6010,
         "aliases": ["cacia"]},
    ],
    "Braga": [
        {"nome": "Centro", "seguranca": 7, "ruido": 7, "comercio": 10,
         "metro_min": None, "bus_min": 3, "comboio_min": 10, "lat": 41.5500, "lon": -8.4270,
         "aliases": ["centro", "baixa"]},
        {"nome": "Gualtar", "seguranca": 8, "ruido": 4, "comercio": 7,
         "metro_min": None, "bus_min": 6, "comboio_min": 15, "lat": 41.5588, "lon": -8.4010,
         "aliases": ["gualtar", "campus de gualtar"]},
        {"nome": "São Victor", "seguranca": 7, "ruido": 6, "comercio": 9,
         "metro_min": None, "bus_min": 4, "comboio_min": 10, "lat": 41.5550, "lon": -8.4200,
         "aliases": ["sao victor"]},
        {"nome": "Sé", "seguranca": 7, "ruido": 6, "comercio": 8,
         "metro_min": None, "bus_min": 4, "comboio_min": 10, "lat": 41.5490, "lon": -8.4270,
         "aliases": ["se"]},
        {"nome": "Real", "seguranca": 7, "ruido": 5, "comercio": 8,
         "metro_min": None, "bus_min": 5, "comboio_min": 12, "lat": 41.5570, "lon": -8.4120,
         "aliases": ["real"]},
        {"nome": "Maximinos", "seguranca": 7, "ruido": 6, "comercio": 8,
         "metro_min": None, "bus_min": 5, "comboio_min": 12, "lat": 41.5450, "lon": -8.4320,
         "aliases": ["maximinos"]},
        {"nome": "Lomar", "seguranca": 8, "ruido": 4, "comercio": 7,
         "metro_min": None, "bus_min": 7, "comboio_min": 15, "lat": 41.5650, "lon": -8.4100,
         "aliases": ["lomar"]},
        {"nome": "Tenões", "seguranca": 8, "ruido": 3, "comercio": 6,
         "metro_min": None, "bus_min": 8, "comboio_min": 18, "lat": 41.5560, "lon": -8.3980,
         "aliases": ["tenoes"]},
        {"nome": "Nogueira", "seguranca": 8, "ruido": 4, "comercio": 6,
         "metro_min": None, "bus_min": 8, "comboio_min": 15, "lat": 41.5350, "lon": -8.4100,
         "aliases": ["nogueira"]},
        {"nome": "Ferreiros", "seguranca": 8, "ruido": 4, "comercio": 7,
         "metro_min": None, "bus_min": 7, "comboio_min": 15, "lat": 41.5300, "lon": -8.4200,
         "aliases": ["ferreiros"]},
    ],
    "Évora": [
        {"nome": "Centro Histórico", "seguranca": 7, "ruido": 6, "comercio": 9,
         "metro_min": None, "bus_min": 4, "comboio_min": 10, "lat": 38.5710, "lon": -7.9100,
         "aliases": ["centro historico", "centro"]},
        {"nome": "Canaviais", "seguranca": 7, "ruido": 5, "comercio": 7,
         "metro_min": None, "bus_min": 6, "comboio_min": 15, "lat": 38.5600, "lon": -7.9250,
         "aliases": ["canaviais"]},
        {"nome": "Malagueira", "seguranca": 7, "ruido": 5, "comercio": 7,
         "metro_min": None, "bus_min": 6, "comboio_min": 15, "lat": 38.5650, "lon": -7.9330,
         "aliases": ["malagueira"]},
        {"nome": "Senhora da Saúde", "seguranca": 8, "ruido": 4, "comercio": 7,
         "metro_min": None, "bus_min": 7, "comboio_min": 15, "lat": 38.5790, "lon": -7.9100,
         "aliases": ["senhora da saude"]},
        {"nome": "Horta das Figueiras", "seguranca": 7, "ruido": 5, "comercio": 7,
         "metro_min": None, "bus_min": 5, "comboio_min": 12, "lat": 38.5720, "lon": -7.8930,
         "aliases": ["horta das figueiras"]},
        {"nome": "Bacelo", "seguranca": 8, "ruido": 4, "comercio": 6,
         "metro_min": None, "bus_min": 8, "comboio_min": 18, "lat": 38.5660, "lon": -7.8780,
         "aliases": ["bacelo"]},
        {"nome": "Mitra", "seguranca": 8, "ruido": 3, "comercio": 5,
         "metro_min": None, "bus_min": 10, "comboio_min": 20, "lat": 38.5328, "lon": -7.9195,
         "aliases": ["mitra", "polo da mitra"]},
    ],
    "Algarve": [
        {"nome": "Faro Centro", "seguranca": 7, "ruido": 6, "comercio": 9,
         "metro_min": None, "bus_min": 4, "comboio_min": 8, "lat": 37.0190, "lon": -7.9320,
         "aliases": ["faro centro", "centro"]},
        {"nome": "Gambelas", "seguranca": 8, "ruido": 4, "comercio": 7,
         "metro_min": None, "bus_min": 6, "comboio_min": 12, "lat": 37.0557, "lon": -7.9761,
         "aliases": ["gambelas", "campus"]},
        {"nome": "Penha", "seguranca": 7, "ruido": 5, "comercio": 7,
         "metro_min": None, "bus_min": 5, "comboio_min": 12, "lat": 37.0303, "lon": -7.9398,
         "aliases": ["penha"]},
        {"nome": "Montenegro", "seguranca": 8, "ruido": 4, "comercio": 6,
         "metro_min": None, "bus_min": 8, "comboio_min": 10, "lat": 37.0300, "lon": -7.9700,
         "aliases": ["montenegro"]},
        {"nome": "Bom João", "seguranca": 7, "ruido": 5, "comercio": 7,
         "metro_min": None, "bus_min": 5, "comboio_min": 10, "lat": 37.0180, "lon": -7.9180,
         "aliases": ["bom joao"]},
        {"nome": "Olhão", "seguranca": 7, "ruido": 6, "comercio": 8,
         "metro_min": None, "bus_min": 10, "comboio_min": 15, "lat": 37.0270, "lon": -7.8410,
         "aliases": ["olhao"]},
        {"nome": "Portimão", "seguranca": 7, "ruido": 7, "comercio": 9,
         "metro_min": None, "bus_min": 12, "comboio_min": 15, "lat": 37.1372, "lon": -8.5382,
         "aliases": ["portimao"]},
        {"nome": "Loulé", "seguranca": 8, "ruido": 5, "comercio": 8,
         "metro_min": None, "bus_min": 12, "comboio_min": 18, "lat": 37.1370, "lon": -8.0210,
         "aliases": ["loule"]},
        {"nome": "Tavira", "seguranca": 8, "ruido": 5, "comercio": 7,
         "metro_min": None, "bus_min": 15, "comboio_min": 20, "lat": 37.1260, "lon": -7.6480,
         "aliases": ["tavira"]},
    ],
}

ZONA_BY_NOME = {c: {z["nome"]: z for z in zonas} for c, zonas in ZONAS.items()}

# ---------------------------------------------------------------------------
# Cache em memória (TTL por cidade + profundidade). Chave: "Cidade|paginas"
# ---------------------------------------------------------------------------
CACHE = {}
LIMITE_SCRAPE = 400   # máximo de anúncios guardados em cache por cidade/depth

# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------
def _normalizar(texto):
    """Remove acentos e passa para minúsculas."""
    texto = unicodedata.normalize("NFD", str(texto))
    texto = "".join(ch for ch in texto if unicodedata.category(ch) != "Mn")
    return texto.lower()


def _slug_cidade(cidade):
    cidade = _normalizar(cidade)
    for slug, nome in CIDADE_SLUG.items():
        if cidade == slug or _normalizar(nome) == cidade:
            return nome
    return "Porto"


def haversine(lat1, lon1, lat2, lon2):
    """Distância em linha reta (km) entre dois pontos — fórmula de Haversine."""
    R = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))


def extrair_preco(texto):
    """Extrai preço em euros (float) de um texto. Lida com separadores de milhar
    e decimais ('120.000 €', '350,00 €'). Ignora se > 5000 ou inválido."""
    if not texto:
        return None
    t = re.sub(r"\s+", " ", texto or "")
    m = re.search(r"(\d[\d.,]*)\s*(?:€|eur|euros|/m[eê]s|mes)", t, re.IGNORECASE)
    if not m:
        m = re.search(r"(?:€|eur)\s*(\d[\d.,]*)", t, re.IGNORECASE)
    if not m:
        return None
    num = m.group(1)
    if "," in num and "." in num:
        num = num.replace(".", "").replace(",", ".")   # 1.500,50 -> 1500.50
    elif "," in num:
        parte = num.split(",")
        if len(parte) == 2 and len(parte[1]) <= 2:
            num = num.replace(",", ".")                 # 350,50 -> 350.50
        else:
            num = num.replace(",", "")                  # 1,500 -> 1500
    else:
        num = num.replace(".", "")                       # 120.000 -> 120000
    try:
        valor = int(float(num))
    except ValueError:
        return None
    if valor <= 0 or valor > 5000:
        return None
    return float(valor)


def determinar_zona(titulo, descricao, cidade):
    """Corresponde o texto a uma zona por palavras-chave. Retorna o nome ou None."""
    cidade = _slug_cidade(cidade)
    texto = _normalizar("%s %s" % (titulo, descricao))
    for zona in ZONAS.get(cidade, []):
        for alias in zona["aliases"]:
            a = _normalizar(alias)
            if re.search(r"(^|\W)" + re.escape(a) + r"(\W|$)", texto):
                return zona["nome"]
    return None


def geocodificar_endereco(endereco, cidade):
    """(lat, lon) para um endereço. Usa a zona (keywords) como fallback rápido
    e Nominatim se GEOCODE_NOMINATIM=1. Último recurso: centro da cidade."""
    cidade = _slug_cidade(cidade)
    zona = determinar_zona(endereco, "", cidade)
    if zona:
        z = ZONA_BY_NOME[cidade][zona]
        return z["lat"], z["lon"]
    if GEOCODE_NOMINATIM:
        try:
            from geopy.geocoders import Nominatim
            loc = Nominatim(user_agent="unicasa-search/1.0").geocode(
                "%s, Portugal" % endereco, timeout=4)
            if loc:
                return loc.latitude, loc.longitude
        except Exception:
            pass
    return CIDADE_CENTRO[cidade]


def _coord_faculdade(nome, cidade):
    if not nome:
        return None
    alvo = _normalizar(nome)
    # procura no dropdown global (todas as cidades)
    for f in UNIVERSIDADES:
        if _normalizar(f["nome"]) == alvo:
            return f["lat"], f["lon"]
    for f in UNIVERSIDADES:
        if alvo in _normalizar(f["nome"]) or _normalizar(f["nome"]) in alvo:
            return f["lat"], f["lon"]
    # fallback: só na cidade atual
    cidade = _slug_cidade(cidade)
    for f in FACULDADES.get(cidade, []):
        if _normalizar(f["nome"]) == alvo:
            return f["lat"], f["lon"]
    return None


def _cidade_da_faculdade(nome):
    """Devolve a cidade a que pertence a faculdade escolhida (dropdown global)."""
    if not nome:
        return None
    alvo = _normalizar(nome)
    for f in UNIVERSIDADES:
        if _normalizar(f["nome"]) == alvo:
            return f["cidade"]
    return None


def calcular_distancia_faculdade(lat, lon, faculdade_nome, cidade):
    """Distância (km, 1 casa decimal) do ponto à faculdade. None se não encontrar."""
    coord = _coord_faculdade(faculdade_nome, cidade)
    if not coord or lat is None or lon is None:
        return None
    return round(haversine(lat, lon, coord[0], coord[1]), 1)


def estrelas_html(nota):
    """Nota 0-10 → string de estrelas (ex: ★★★★☆)."""
    if nota is None:
        return "☆☆☆☆☆"
    cheias = int(round(max(0, min(10, nota)) / 2))
    return "★" * cheias + "☆" * (5 - cheias)


def badge_nota(nota):
    """Classe CSS da nota: nota-boa (>=8), nota-media (>=5), nota-mau."""
    if nota is None:
        return "nota-mau"
    if nota >= 8:
        return "nota-boa"
    if nota >= 5:
        return "nota-media"
    return "nota-mau"


def extrair_data_disponibilidade(titulo, descricao):
    """Deteta 'disponível a partir de Setembro 2026' → 'Disponivel em Setembro 2026',
    e também 'Disponível em: 31/10/2026'."""
    texto = _normalizar("%s %s" % (titulo, descricao))
    # data no formato dd/mm/yyyy
    m = re.search(r"dispon[ií]vel\s*(?:a\s*partir\s*de|em|para)?\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})", texto)
    if m:
        return "Disponivel em " + m.group(1)
    m = re.search(r"dispon[ií]vel\s*(?:a\s*partir\s*de|em|para)?\s*:?\s*([a-zçãâáéêíóôú]+\s+\d{4})", texto)
    if m:
        val = m.group(1).strip()
        if val and val != "agora":
            return "Disponivel em " + val.title()
    if re.search(r"dispon[ií]vel", texto):
        return "Disponivel"
    return None


def _limpar_descricao_idealista(desc):
    """Remove o boilerplate do Idealista ('Disponível em: 31/10/2026. Reserve em
    linha... COMO É QUE FUNCIONA... *********') e devolve só o texto útil."""
    if not desc:
        return ""
    d = desc
    for pat in (r"dispon[ií]vel\s*em\s*:?\s*\d{1,2}/\d{1,2}/\d{4}",
                r"reserve\s+em\s+linha", r"link\s+adicional",
                r"como\s+[eé]\s+que\s+funciona", r"\*{3,}"):
        m = re.search(pat, d, re.IGNORECASE)
        if m:
            d = d[:m.start()]
    d = re.sub(r"\*+", "", d)
    return _limpar(d)[:220]


_MESES_PT = {"janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4, "maio": 5,
             "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
             "novembro": 11, "dezembro": 12}


def _parse_data_pt(texto):
    """Converte '23 de julho de 2026' (ou '23/07/2026') em (timestamp, '23/07/2026')."""
    t = _normalizar(texto)
    m = re.search(r"(\d{1,2})\s+de\s+([a-zçãâáéêíóôú]+)\s+de\s+(\d{4})", t)
    if m:
        dia, mes, ano = int(m.group(1)), _MESES_PT.get(m.group(2)), int(m.group(3))
        if mes:
            try:
                dt = datetime(ano, mes, dia)
                return dt.timestamp(), dt.strftime("%d/%m/%Y")
            except ValueError:
                return None, None
    try:
        dt = datetime.strptime(str(texto).strip()[:10], "%d/%m/%Y")
        return dt.timestamp(), dt.strftime("%d/%m/%Y")
    except ValueError:
        return None, None


def _data_ts(texto):
    """Timestamp a partir de datas relativas ('hoje', 'ontem', 'há X dias') ou ISO."""
    agora = time.time()
    if not texto:
        return agora
    t = _normalizar(texto)
    if re.search(r"\bhoje\b", t):
        return agora
    if re.search(r"\bontem\b", t):
        return agora - 86400
    m = re.search(r"h[aá]\s+(\d+)\s*(dias?|horas?|min)", t)
    if m:
        n = int(m.group(1))
        unidade = m.group(2)
        seg = {"dia": 86400, "dias": 86400, "hora": 3600, "horas": 3600,
               "min": 60}[unidade] if unidade in {"dia", "dias", "hora", "horas", "min"} else 86400
        return agora - n * seg
    ts, _disp = _parse_data_pt(texto)
    if ts:
        return ts
    try:
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                return datetime.strptime(str(texto)[:19], fmt).timestamp()
            except ValueError:
                continue
    except Exception:
        pass
    return agora


def _limpar(texto):
    return re.sub(r"\s+", " ", texto or "").strip()


# Cidades/distritos portugueses (para filtrar anúncios fora da cidade pesquisada).
# Nota: zonas da área metropolitana do Porto (Gaia, Maia, Matosinhos, Gondomar)
# estão de propósito fora desta lista para não serem rejeitadas.
OUTRAS_CIDADES = [
    "viseu", "aveiro", "braga", "braganca", "castelo branco", "coimbra",
    "evora", "faro", "guarda", "leiria", "lisboa", "portalegre", "santarem",
    "setubal", "viana do castelo", "vila real", "portimao", "algarve",
    "guimaraes", "covilha", "lamego", "figueira da foz", "peniche", "nazare",
    "caldas da rainha", "torres vedras", "sintra", "cascais", "amadora",
    "loures", "seixal", "almada", "odivelas", "oeiras", "esposende",
]

# Tokens válidos por cidade (não devem ser tratados como "outra cidade").
CIDADE_TOKEN = {
    "Porto": {"porto", "gaia", "vila nova de gaia", "matosinhos", "maia", "gondomar"},
    "Lisboa": {"lisboa"},
    "Coimbra": {"coimbra"},
    "Vila Real": {"vila real"},
    "Aveiro": {"aveiro"},
    "Braga": {"braga"},
    "Évora": {"evora"},
    "Algarve": {"algarve", "faro", "portimao", "loule", "olhao", "tavira",
                "albufeira", "lagos", "lagoa", "silves", "vilamoura", "quarteira"},
}


def _fora_da_cidade(texto, cidade):
    """True se o texto referencia claramente outra cidade/distrito (ex: uma casa
    de Viseu a aparecer na pesquisa de Porto)."""
    t = _normalizar(texto)
    validos = CIDADE_TOKEN.get(cidade, {_normalizar(cidade)})
    for c in OUTRAS_CIDADES:
        if c in validos:
            continue
        if re.search(r"(^|\W)" + re.escape(c) + r"(\W|$)", t):
            return True
    return False


def _criar_anuncio(titulo, preco, link, data_texto, descricao, imagem, fonte, cidade,
                   disponibilidade=None):
    if preco is None:
        return None
    texto = "%s %s" % (titulo, descricao)
    if _fora_da_cidade(texto, cidade):
        return None
    lat, lon = geocodificar_endereco(texto, cidade)
    zona = determinar_zona(titulo, descricao, cidade)
    return {
        "titulo": _limpar(titulo),
        "preco": float(preco),
        "link": _limpar(link),
        "data": _limpar(data_texto) or "Hoje",
        "data_ts": _data_ts(data_texto),
        "disponibilidade": disponibilidade,
        "imagem": _limpar(imagem),
        "fonte": fonte,
        "zona": zona,
        "lat": lat,
        "lon": lon,
        "descricao": _limpar(descricao),
    }


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------
def _obter(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
    except requests.RequestException:
        return None
    return None


IMOVIRTUAL_URLS = {
    "porto": "https://www.imovirtual.com/pt/resultados/arrendar/quarto/porto/porto",
    "lisboa": "https://www.imovirtual.com/pt/resultados/arrendar/quarto/lisboa/lisboa",
    "coimbra": "https://www.imovirtual.com/pt/resultados/arrendar/quarto/coimbra/coimbra",
    "vila real": "https://www.imovirtual.com/pt/resultados/arrendar/quarto/vila-real/vila-real",
    "aveiro": "https://www.imovirtual.com/pt/resultados/arrendar/quarto/aveiro/aveiro",
    "braga": "https://www.imovirtual.com/pt/resultados/arrendar/quarto/braga/braga",
    "evora": "https://www.imovirtual.com/pt/resultados/arrendar/quarto/evora/evora",
    "algarve": "https://www.imovirtual.com/pt/resultados/arrendar/quarto/faro/",
}


def _imo_data_anuncio(texto_card):
    t = _normalizar(texto_card)
    if re.search(r"adicionado\w*\s+hoje", t):
        return "Hoje"
    if re.search(r"adicionado\w*\s+ontem", t):
        return "Ontem"
    m = re.search(r"adicionado\w*\s+h[aá]\s+(\d+)\s*(dias?|horas?)", t)
    if m:
        return "há %s %s" % (m.group(1), m.group(2))
    return ""


def scrape_imovirtual(cidade, paginas=MAX_PAGES):
    """Scraping HTML do Imovirtual (página de quartos), N páginas × 25."""
    cidade = _slug_cidade(cidade)
    base = IMOVIRTUAL_URLS.get(_normalizar(cidade))
    if not base:
        return []
    anuncios = []
    for pagina in range(1, paginas + 1):
        url = base
        if pagina > 1:
            url += ("&" if "?" in url else "?") + "page=%d" % pagina
        html = _obter(url)
        if not html:
            break
        soup = BeautifulSoup(html, "lxml")
        itens = [art for art in soup.find_all("article")
                 if art.select_one('[data-cy="listing-item-link"]')]
        if not itens:
            itens = soup.select('div[data-cy="search.listing.organic"] article')
        itens = itens[:MAX_ARTICLES_PER_PAGE]
        if not itens:
            break
        for item in itens:
            link_el = (item.select_one('[data-cy="listing-item-link"]')
                       or item.select_one('a[href*="/pt/anuncio/"]')
                       or item.find("a", href=True))
            if not link_el:
                continue
            link = link_el.get("href", "") or ""
            if link.startswith("/"):
                link = "https://www.imovirtual.com" + link
            titulo = _limpar(item.select_one('[data-cy="listing-item-title"]').get_text(" ", strip=True)
                             if item.select_one('[data-cy="listing-item-title"]') else "")
            if not titulo:
                titulo = _limpar(link_el.get("title") or link_el.get_text(" ", strip=True))
            preco_el = (item.select_one('[data-cy="listing-item-price"]')
                        or item.select_one('span:has(€)') or item.select_one('[class*="price"]'))
            preco = extrair_preco(preco_el.get_text(" ", strip=True) if preco_el else None)
            if preco is None:
                preco = extrair_preco(item.get_text(" ", strip=True))
            if preco is None:
                continue
            local_el = item.select_one('[data-cy="advert-card-address"]')
            local = local_el.get_text(" ", strip=True) if local_el else ""
            desc = _limpar(local)
            img = ""
            img_el = item.find("img")
            if img_el:
                img = img_el.get("src") or img_el.get("data-src") or img_el.get("data-lazy") or ""
            texto_card = item.get_text(" ", strip=True)
            data_texto = _imo_data_anuncio(texto_card)
            disp = extrair_data_disponibilidade(titulo, texto_card)
            an = _criar_anuncio(titulo, preco, link, data_texto, desc, img,
                                "Imovirtual", cidade, disponibilidade=disp)
            if an:
                anuncios.append(an)
        if len(anuncios) >= LIMITE_SCRAPE:
            break
    return anuncios


CUSTOJUSTO_URLS = {
    "porto": "https://www.custojusto.pt/porto/imobiliario/quartos",
    "lisboa": "https://www.custojusto.pt/lisboa/imobiliario/quartos",
    "coimbra": "https://www.custojusto.pt/coimbra/imobiliario/quartos",
    "vila real": "https://www.custojusto.pt/vila-real/imobiliario/quartos",
    "aveiro": "https://www.custojusto.pt/aveiro/imobiliario/quartos",
    "braga": "https://www.custojusto.pt/braga/imobiliario/quartos",
    "evora": "https://www.custojusto.pt/evora/imobiliario/quartos",
    "algarve": "https://www.custojusto.pt/faro/imobiliario/quartos",
}

OLX_URLS = {
    "porto": "https://www.olx.pt/imoveis/q-quarto-porto/",
    "lisboa": "https://www.olx.pt/imoveis/q-quarto-lisboa/",
    "coimbra": "https://www.olx.pt/imoveis/q-quarto-coimbra/",
    "vila real": "https://www.olx.pt/imoveis/q-quarto-vila-real/",
    "aveiro": "https://www.olx.pt/imoveis/q-quarto-aveiro/",
    "braga": "https://www.olx.pt/imoveis/q-quarto-braga/",
    "evora": "https://www.olx.pt/imoveis/q-quarto-evora/",
    "algarve": "https://www.olx.pt/imoveis/q-quarto-faro/",
}

IDEALISTA_URLS = {
    "porto": "https://www.idealista.pt/arrendar-quarto/porto/",
    "lisboa": "https://www.idealista.pt/arrendar-quarto/lisboa/",
    "coimbra": "https://www.idealista.pt/arrendar-quarto/coimbra/",
    "vila real": "https://www.idealista.pt/arrendar-quarto/vila-real/",
    "aveiro": "https://www.idealista.pt/arrendar-quarto/aveiro/",
    "braga": "https://www.idealista.pt/arrendar-quarto/braga/",
    "evora": "https://www.idealista.pt/arrendar-quarto/evora/",
    "algarve": "https://www.idealista.pt/arrendar-quarto/faro/",
}


def _cj_str(v):
    if v is None:
        return ""
    if isinstance(v, dict):
        return v.get("name") or v.get("label") or ""
    return str(v)


def _cj_preco(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if v >= 50 and v <= 5000 else None
    p = extrair_preco(str(v))
    return p if (p is not None and 50 <= p <= 5000) else None


def _cj_data(v):
    if isinstance(v, (int, float)):
        ts = v / 1000.0 if v > 1e12 else v
        try:
            return datetime.fromtimestamp(ts).strftime("%d/%m/%Y")
        except Exception:
            return ""
    s = _cj_str(v)
    if not s:
        return ""
    # ISO '2026-08-04T10:14:55Z' -> '04/08/2026'
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            return ""
    return s


def scrape_custojusto(cidade, paginas=MAX_PAGES):
    """Extrai anúncios do JSON embutido do Next.js (__NEXT_DATA__), N páginas × 30."""
    cidade = _slug_cidade(cidade)
    url = CUSTOJUSTO_URLS.get(_normalizar(cidade))
    if not url:
        return []
    anuncios = []
    vistos = set()
    for pagina in range(1, paginas + 1):
        u = url + (("?page=%d" % pagina) if pagina > 1 else "")
        html = _obter(u)
        if not html:
            break
        soup = BeautifulSoup(html, "lxml")
        script = soup.find("script", id="__NEXT_DATA__")
        if not script:
            break
        try:
            dados = json.loads(script.string or script.get_text())
        except (ValueError, TypeError):
            break
        page = (dados.get("props") or {}).get("pageProps") or {}
        itens = page.get("listItems") or []
        if not itens:
            break
        for it in itens[:MAX_CUSTOJUSTO]:
            titulo = _cj_str(it.get("title"))
            preco = _cj_preco(it.get("price"))
            if not titulo or preco is None:
                continue
            link = _cj_str(it.get("url"))
            if link.startswith("/"):
                link = "https://www.custojusto.pt" + link
            loc = it.get("locationNames") or {}
            local = " ".join(str(v) for v in loc.values() if v)
            corpo = _cj_str(it.get("body"))
            desc = _limpar("%s %s" % (corpo, local))
            img = _cj_str(it.get("imageFullURL"))
            data_texto = _cj_data(it.get("listTime"))
            chave = titulo + str(preco)
            if chave in vistos:
                continue
            vistos.add(chave)
            disp = extrair_data_disponibilidade(titulo, corpo)
            an = _criar_anuncio(titulo, preco, link, data_texto, desc, img,
                                "CustoJusto", cidade, disponibilidade=disp)
            if an:
                anuncios.append(an)
        if len(anuncios) >= LIMITE_SCRAPE:
            break
    return anuncios


def _olx_data_texto(loc_date_texto):
    """Extrai a data do OLX. 'Pedrouços - 23 de julho de 2026' → '23/07/2026';
    também trata 'hoje', 'ontem' e 'há X dias'."""
    if not loc_date_texto:
        return ""
    parte = loc_date_texto
    if " - " in loc_date_texto:
        parte = loc_date_texto.split(" - ", 1)[1]
    t = _normalizar(parte)
    if re.search(r"\bhoje\b", t):
        return "Hoje"
    if re.search(r"\bontem\b", t):
        return "Ontem"
    m = re.search(r"h[aá]\s+(\d+)\s*(dias?|horas?)", t)
    if m:
        return "há %s %s" % (m.group(1), m.group(2))
    _ts, disp = _parse_data_pt(parte)
    if disp:
        return disp
    return ""


def _normaliza_url_olx(img):
    if not img:
        return ""
    if img.startswith("/") or img.startswith("data:"):
        return ""
    if ";s=216x152;q=50" in img:
        img = img.replace(";s=216x152;q=50", ";s=800x600;q=70")
    else:
        img = re.sub(r";s=\d+x\d+;q=\d+", ";s=800x600;q=70", img)
    return img


def _imagem_olx(img_el):
    """Extrai a imagem real do card do OLX. O primeiro <img> usa lazy-load: o src
    é um placeholder e a imagem verdadeira está no srcset. Ignora no_thumbnail."""
    if not img_el:
        return ""
    srcset = img_el.get("srcset") or ""
    if srcset:
        urls = []
        for parte in srcset.split(","):
            parte = parte.strip()
            if parte:
                urls.append(parte.split()[0])
        if urls:
            # a última entrada costuma ser a maior resolução
            img = _normaliza_url_olx(urls[-1])
            if img:
                return img
    img = img_el.get("src") or img_el.get("data-src") or ""
    return _normaliza_url_olx(img)


def scrape_olx(cidade, paginas=MAX_PAGES):
    """Scraping do OLX Portugal (quartos) — mesmo motor do Imovirtual, ativo.

    Nota: o OLX partilha a plataforma do grupo com o Imovirtual; as páginas de
    pesquisa respondem a pedidos normais (sem challenge de Cloudflare aqui)."""
    cidade = _slug_cidade(cidade)
    url = OLX_URLS.get(_normalizar(cidade))
    if not url:
        return []
    anuncios = []
    vistos = set()
    for pagina in range(1, paginas + 1):
        u = url + (("?page=%d" % pagina) if pagina > 1 else "")
        html = _obter(u)
        if not html:
            break
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select('[data-cy="l-card"]')
        if not cards:
            break
        for card in cards:
            link_el = card.select_one('a[href*="/anuncio/"]')
            if not link_el:
                continue
            link = link_el.get("href", "") or ""
            if link.startswith("/"):
                link = "https://www.olx.pt" + link
            title_el = card.select_one('[data-testid="ad-card-title"]')
            titulo = title_el.get_text(" ", strip=True) if title_el else ""
            if not titulo:
                titulo = link_el.get("title") or link_el.get_text(" ", strip=True)
            price_el = card.select_one('[data-testid="ad-price"]')
            preco = extrair_preco(price_el.get_text(" ", strip=True) if price_el else None)
            if preco is None:
                preco = extrair_preco(card.get_text(" ", strip=True))
            if preco is None:
                continue
            loc_date_el = card.select_one('[data-testid="location-date"]')
            loc_date = loc_date_el.get_text(" ", strip=True) if loc_date_el else ""
            data_texto = _olx_data_texto(loc_date)
            local = loc_date.split(" - ")[0] if " - " in loc_date else loc_date
            img = _imagem_olx(card.find("img"))
            card_text = card.get_text(" ", strip=True)
            disp = extrair_data_disponibilidade(titulo, card_text)
            chave = _normalizar(titulo) + str(preco)
            if chave in vistos:
                continue
            vistos.add(chave)
            an = _criar_anuncio(titulo, preco, link, data_texto, local, img,
                                "OLX", cidade, disponibilidade=disp)
            if an:
                anuncios.append(an)
        if len(anuncios) >= LIMITE_SCRAPE:
            break
    return anuncios


def _idealista_html_com_playwright(url):
    """Abre a página do Idealista num Chromium real (channel='chromium', que passa
    o challenge do DataDome, ao contrário do headless-shell). Devolve o HTML final
    ou None se Playwright não estiver disponível."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    html = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                channel="chromium",
                args=["--disable-blink-features=AutomationControlled"])
            ctx = browser.new_context(
                locale="pt-PT",
                user_agent=HEADERS["User-Agent"],
                viewport={"width": 1366, "height": 900})
            ctx.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # espera o DataDome resolver o challenge (o título deixa de ser a capa)
            try:
                page.wait_for_function(
                    "document.title && !document.title.includes('idealista.pt')",
                    timeout=30000)
            except Exception:
                pass
            # fecha o banner de cookies se aparecer
            try:
                if page.locator("#didomi-notice-agree-button").count():
                    page.locator("#didomi-notice-agree-button").click(timeout=4000)
                    page.wait_for_timeout(1500)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            html = page.content()
            browser.close()
    except Exception:
        html = None
    return html


def _parse_idealista(html, cidade):
    soup = BeautifulSoup(html, "lxml")
    itens = soup.select("article.item")
    anuncios = []
    vistos = set()
    for item in itens:
        link_el = item.select_one('a.item-link[href*="/imovel/"]') or item.select_one("a.item-link")
        if not link_el:
            continue
        link = link_el.get("href", "") or ""
        if link.startswith("/"):
            link = "https://www.idealista.pt" + link
        titulo = _limpar(link_el.get("title") or link_el.get_text(" ", strip=True))
        if not titulo:
            h = item.find(["h1", "h2", "h3", "h4"])
            titulo = _limpar(h.get_text(" ", strip=True) if h else "")
        price_el = item.select_one(".item-price") or item.select_one(".price-row")
        preco = extrair_preco(price_el.get_text(" ", strip=True) if price_el else None)
        if preco is None:
            continue
        loc_el = item.select_one(".item-location")
        loc = _limpar(loc_el.get_text(" ", strip=True)) if loc_el else ""
        desc_el = item.select_one(".item-description")
        desc = _limpar_descricao_idealista(desc_el.get_text(" ", strip=True)) if desc_el else ""
        if not loc and not desc:
            desc = titulo
        img = ""
        img_el = item.select_one(".item-multimedia img") or item.find("img")
        if img_el:
            # mantém o URL original (o '/blur/' devolve a miniatura válida)
            img = img_el.get("src") or img_el.get("data-src") or ""
        card_text = item.get_text(" ", strip=True)
        disp = extrair_data_disponibilidade(titulo, card_text)
        chave = _normalizar(titulo) + str(preco)
        if chave in vistos:
            continue
        vistos.add(chave)
        an = _criar_anuncio(titulo, preco, link, "", loc, img, "Idealista",
                            cidade, disponibilidade=disp)
        if an:
            an["descricao"] = desc
            anuncios.append(an)
    return anuncios[:LIMITE_SCRAPE]


def scrape_idealista(cidade, paginas=1):
    """Idealista — bloqueado por DataDome CAPTCHA. Tenta obter via Playwright.

    Ativar com ENABLE_IDEALISTA=1 + 'pip install playwright' + 'playwright install
    chromium'. Se não estiver ativo/instalado, devolve [] (sem bloquear o site).
    Como cada página exige abrir um browser, limita-se a min(paginas, 2) páginas."""
    if not ENABLE_IDEALISTA:
        return []
    cidade = _slug_cidade(cidade)
    base = IDEALISTA_URLS.get(_normalizar(cidade))
    if not base:
        return []
    paginas = max(1, min(paginas, 2))
    anuncios = []
    vistos = set()
    for pagina in range(1, paginas + 1):
        url = base + (("?pagina=%d" % pagina) if pagina > 1 else "")
        html = _idealista_html_com_playwright(url)
        if not html or "datadome" in html.lower() or "enable JS" in html:
            break
        for an in _parse_idealista(html, cidade):
            chave = (an["titulo"].lower(), an["preco"])
            if chave in vistos:
                continue
            vistos.add(chave)
            anuncios.append(an)
        if len(anuncios) >= LIMITE_SCRAPE:
            break
    return anuncios


def scrape_housinganywhere(cidade):
    # Desativado — renderiza em JavaScript, requer Playwright/Camoufox
    return []


def scrape_spotahome(cidade):
    # Desativado — renderiza em JavaScript, requer Playwright/Camoufox
    return []


FONTES_ATIVAS = {"Imovirtual": scrape_imovirtual,
                 "OLX": scrape_olx,
                 "CustoJusto": scrape_custojusto}
if ENABLE_IDEALISTA:
    FONTES_ATIVAS["Idealista"] = scrape_idealista


def carregar_anuncios(cidade, paginas=2):
    """Anúncios da cidade usando cache (TTL de 30 min), por cidade + profundidade.

    Junta todos os anúncios das fontes (sem interleave) num pool comum; a ordenação
    e o limite final são aplicados na rota. Guarda até LIMITE_SCRAPE por cache."""
    cidade = _slug_cidade(cidade)
    chave = "%s|%d" % (cidade, paginas)
    agora = time.time()
    entrada = CACHE.get(chave)
    if entrada and (agora - entrada["timestamp"]) < CACHE_TTL:
        return entrada["anuncios"], entrada["fonte"], entrada["timestamp"]

    brutos = []
    fonte_usada = []
    for nome, func in FONTES_ATIVAS.items():
        try:
            lista = func(cidade, paginas)
        except Exception:
            lista = []
        if lista:
            fonte_usada.append(nome)
            brutos.append(lista)

    # deduplica por (título normalizado, preço) e junta tudo
    merged = []
    vistos = set()
    for lista in brutos:
        for an in lista:
            chave_d = (an["titulo"].lower(), an["preco"])
            if chave_d in vistos:
                continue
            vistos.add(chave_d)
            merged.append(an)
        if len(merged) >= LIMITE_SCRAPE:
            break
    merged = merged[:LIMITE_SCRAPE]

    # se nenhuma fonte retornou anúncios, não guarda em cache (para tentar de novo)
    if not merged:
        return [], fonte_usada, agora

    CACHE[chave] = {"anuncios": merged, "timestamp": agora, "fonte": fonte_usada}
    return merged, fonte_usada, agora


def invalidar_cache(cidade, paginas=None):
    cidade = _slug_cidade(cidade)
    if paginas is not None:
        CACHE.pop("%s|%d" % (cidade, paginas), None)
    else:
        for k in list(CACHE):
            if k.startswith(cidade + "|"):
                CACHE.pop(k, None)


# ---------------------------------------------------------------------------
# Flask app + template
# ---------------------------------------------------------------------------
app = Flask(__name__)


def _aplicar_filtros(anuncios, cidade, faculdade, preco_min, preco_max, dist_max,
                     seg_min, tranquilo_min, com_min):
    """Aplica filtros. Nos três casos 'quanto mais alto, melhor':
    seguranca >= seg_min, tranquilidade (=10 - ruido) >= tranquilo_min, comercio >= com_min."""
    zona_map = ZONA_BY_NOME.get(cidade, {})
    resultado = []
    for a in anuncios:
        if preco_min is not None and a["preco"] < preco_min:
            continue
        if preco_max is not None and a["preco"] > preco_max:
            continue
        z = zona_map.get(a["zona"]) if a["zona"] else None
        seg = z["seguranca"] if z else None
        rui = z["ruido"] if z else None
        tranquilo = (10 - rui) if rui is not None else None
        com = z["comercio"] if z else None
        if seg_min is not None and (seg is None or seg < seg_min):
            continue
        if tranquilo_min is not None and (tranquilo is None or tranquilo < tranquilo_min):
            continue
        if com_min is not None and (com is None or com < com_min):
            continue
        dist = calcular_distancia_faculdade(a["lat"], a["lon"], faculdade, cidade)
        if dist_max is not None and (dist is None or dist > dist_max):
            continue
        item = dict(a)
        item["distancia"] = dist
        item["seguranca"] = seg
        item["ruido"] = rui
        item["tranquilo"] = tranquilo
        item["comercio"] = com
        item["metro_min"] = z["metro_min"] if z else None
        item["bus_min"] = z["bus_min"] if z else None
        item["comboio_min"] = z["comboio_min"] if z else None
        resultado.append(item)
    return resultado


def _ordenar(anuncios, ordenar, faculdade, cidade):
    if ordenar == "preco_asc":
        anuncios.sort(key=lambda a: (a["preco"], a["data_ts"]))
    elif ordenar == "preco_desc":
        anuncios.sort(key=lambda a: (a["preco"], a["data_ts"]), reverse=True)
    elif ordenar == "distancia":
        anuncios.sort(key=lambda a: (a["distancia"] if a["distancia"] is not None else 1e9,
                                     a["data_ts"]))
    elif ordenar == "seguranca":
        anuncios.sort(key=lambda a: (a["seguranca"] if a["seguranca"] is not None else -1,
                                     a["data_ts"]), reverse=True)
    elif ordenar == "ruido_asc":
        anuncios.sort(key=lambda a: (a["ruido"] if a["ruido"] is not None else 11,
                                     a["data_ts"]))
    elif ordenar == "comercio":
        anuncios.sort(key=lambda a: (a["comercio"] if a["comercio"] is not None else -1,
                                     a["data_ts"]), reverse=True)
    else:
        anuncios.sort(key=lambda a: a["data_ts"], reverse=True)


def _balanceado(anuncios, limite):
    """Garante uma mistura de fontes: cada fonte contribui no máximo quota
    anúncios (os melhores segundo a ordenação já aplicada). Evita que uma única
    fonte domine e que outras desapareçam dos resultados."""
    if len(anuncios) <= limite:
        return anuncios
    por_fonte = {}
    for a in anuncios:
        por_fonte.setdefault(a["fonte"], []).append(a)
    n = len(por_fonte)
    quota = max(1, limite // n)
    selecionados = []
    for lista in por_fonte.values():
        selecionados.extend(lista[:quota])
    return selecionados[:limite]


def _float(v):
    try:
        return float(v) if v else None
    except (TypeError, ValueError):
        return None


def _int(v):
    try:
        return int(float(v)) if v else None
    except (TypeError, ValueError):
        return None


HTML_TEMPLATE = """<!doctype html>
<html lang="pt">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aloja-Te — Encontra quarto sem complicações</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
<style>
  :root{
    --grad:linear-gradient(135deg,#6366f1 0%,#8b5cf6 45%,#a855f7 100%);
    --grad-suave:linear-gradient(135deg,#eef2ff,#f5f3ff);
    --primario:#6366f1; --primario-escuro:#4f46e5; --violeta:#8b5cf6;
    --laranja:#fb923c; --laranja-escuro:#f97316;
    --fundo:#f6f7fe; --texto:#334155; --texto-suave:#64748b;
    --sombra:0 .3rem 1.2rem rgba(99,102,241,.10);
    --sombra-hover:0 .7rem 1.6rem rgba(139,92,246,.20);
  }
  body{background:var(--fundo);color:var(--texto);}
  .navbar-unicasa{background:var(--grad);box-shadow:0 .25rem 1rem rgba(139,92,246,.25);}
  .navbar-unicasa .navbar-brand{letter-spacing:.3px;}
  .brand-casa{color:#ffd166;font-weight:800;}
  .stats-bar{background:#fff;border:1px solid #e9e8fb;border-radius:.75rem;font-size:.85rem;color:var(--texto);box-shadow:var(--sombra);}
  .filter-card{background:#fff;border:none;box-shadow:var(--sombra);border-radius:1rem;}
  .slider-val{font-weight:700;color:var(--primario);}
  .card-ad{border:none;box-shadow:var(--sombra);border-radius:1rem;transition:transform .18s ease,box-shadow .18s ease;overflow:hidden;}
  .card-ad:hover{transform:translateY(-4px);box-shadow:var(--sombra-hover);}
  .ad-img{height:150px;width:100%;object-fit:cover;background:#e9eefb;}
  .ad-img-ph{height:150px;width:100%;display:flex;align-items:center;justify-content:center;background:var(--grad-suave);}
  .badge-fonte{position:absolute;top:.45rem;left:.45rem;padding:.2rem .5rem;border-radius:.5rem;font-size:.68rem;font-weight:700;box-shadow:0 .15rem .4rem rgba(0,0,0,.2);}
  .badge-data{position:absolute;top:.45rem;right:.45rem;background:rgba(30,27,75,.65);color:#fff;padding:.2rem .5rem;border-radius:.5rem;font-size:.68rem;backdrop-filter:blur(2px);}
  .ad-titulo{font-weight:700;font-size:.95rem;color:#1e1b4b;min-height:2.5rem;}
  .ad-preco{font-size:1.35rem;font-weight:800;color:var(--primario-escuro);}
  .ad-preco small{font-size:.8rem;color:var(--texto-suave);font-weight:500;}
  .dist-box{background:linear-gradient(90deg,#eef2ff,#ede9fe);border-radius:.5rem;padding:.3rem .55rem;font-size:.78rem;font-weight:600;color:var(--primario-escuro);}
  .ad-desc{font-size:.8rem;color:var(--texto-suave);}
  .zona-notas{border:1px dashed #d8d5f6;border-radius:.6rem;padding:.5rem .6rem;background:#fbfaff;}
  .nota-boa{color:#16a34a;font-weight:700;}
  .nota-media{color:#d97706;font-weight:700;}
  .nota-mau{color:#dc2626;font-weight:700;}
  .transporte-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:.25rem;font-size:.74rem;color:var(--texto-suave);}
  .notas-icones{display:flex;justify-content:space-between;gap:.5rem;}
  .nota-icone{display:inline-flex;align-items:center;gap:.25rem;font-size:.8rem;font-weight:600;}
  .nota-icone i{font-style:normal;}
  .btn-laranja{background:linear-gradient(90deg,#fb923c,#f97316);border:none;color:#fff;font-weight:700;}
  .btn-laranja:hover{background:linear-gradient(90deg,#f97316,#ea580c);color:#fff;transform:translateY(-1px);box-shadow:0 .3rem .8rem rgba(249,115,22,.35);}
  .badge-zona{background:#eef2ff;color:var(--primario-escuro);font-size:.72rem;font-weight:600;}
  .fontes-legend{font-size:.78rem;color:var(--texto-suave);}
  .fontes-legend .dot{display:inline-block;width:.6rem;height:.6rem;border-radius:50%;margin-right:.25rem;vertical-align:middle;}
  footer{font-size:.85rem;color:var(--texto-suave);}
</style>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark navbar-unicasa mb-3">
  <div class="container">
    <a class="navbar-brand fw-bold fs-4" href="{{ url_for('index') }}">Aloja<span class="brand-casa">-Te</span></a>
    <span class="navbar-text text-white d-none d-md-inline" style="font-size:1rem;font-weight:500;opacity:.95;border-left:2px solid rgba(255,255,255,.4);padding-left:.75rem;">Encontra quarto sem complicações</span>
  </div>
</nav>

<div class="container pb-5">

  <div class="stats-bar d-flex flex-wrap justify-content-between align-items-center px-3 py-2 mb-3">
    <span><strong>{{ total }}</strong> anúncios em <strong>{{ cidade }}</strong>{% if faculdade %} · {{ faculdade }}{% endif %}</span>
    <span>Cache: {{ cache_min }} minutos · Atualizado: {{ atualizado }}</span>
  </div>

  {% if alerta %}
  <div class="alert {{ alerta.classe }} d-flex justify-content-between align-items-center py-2">
    <span>{{ alerta.texto }}</span>
    <a href="{{ alerta.link }}" class="fw-bold text-decoration-underline">{{ alerta.acao }}</a>
  </div>
  {% endif %}

  <!-- Filtros -->
  <div class="card filter-card mb-4">
    <div class="card-body">
      <form method="get" action="{{ url_for('index') }}" id="filtros">
        <div class="row g-3">
          <div class="col-md-4">
            <label class="form-label small" for="cidade">Cidade</label>
            <select id="cidade" name="cidade" class="form-select form-select-sm">
              {% for c in cidades %}<option value="{{ c }}" {% if c == cidade %}selected{% endif %}>{{ c }}</option>{% endfor %}
              <option disabled>──────────────</option>
              {% for c in cidades_extra %}<option value="{{ c }}" {% if c == cidade %}selected{% endif %}>{{ c }}</option>{% endfor %}
            </select>
          </div>
          <div class="col-md-8">
            <label class="form-label small" for="faculdade">Faculdade (para distância)</label>
            <select id="faculdade" name="faculdade" class="form-select form-select-sm">
              <option value="">— Todas / sem referência —</option>
              {% for g in universidades_grupos %}
              <optgroup label="{{ g.cidade }}">
                {% for f in g.faculdades %}<option value="{{ f.nome }}" data-cidade="{{ g.cidade }}" {% if f.nome == faculdade %}selected{% endif %}>{{ f.nome }}</option>{% endfor %}
              </optgroup>
              {% endfor %}
            </select>
          </div>
        </div>
        <div class="row g-3 mt-0">
          <div class="col-md-2">
            <label class="form-label small" for="preco_min">Preço mín (€)</label>
            <input type="number" id="preco_min" name="preco_min" class="form-control form-control-sm" min="0" step="10" value="{{ preco_min or '' }}">
          </div>
          <div class="col-md-2">
            <label class="form-label small" for="preco_max">Preço máx (€)</label>
            <input type="number" id="preco_max" name="preco_max" class="form-control form-control-sm" min="0" step="10" value="{{ preco_max or '' }}">
          </div>
          <div class="col-md-2">
            <label class="form-label small" for="dist_max">Dist. máx à faculdade (km, linha reta)</label>
            <input type="number" id="dist_max" name="dist_max" class="form-control form-control-sm" min="0" step="0.1" value="{{ dist_max or '' }}">
          </div>
          <div class="col-md-3">
            <label class="form-label small" for="paginas">Profundidade de pesquisa</label>
            <select id="paginas" name="paginas" class="form-select form-select-sm">
              <option value="2" {% if paginas == 2 %}selected{% endif %}>Padrão (2 páginas)</option>
              <option value="5" {% if paginas == 5 %}selected{% endif %}>Aprofundado (5 páginas)</option>
            </select>
          </div>
          <div class="col-md-3">
            <label class="form-label small" for="ordenar">Ordenar por</label>
            <select id="ordenar" name="ordenar" class="form-select form-select-sm">
              <option value="" {% if not ordenar %}selected{% endif %}>Mais recentes</option>
              <option value="preco_asc" {% if ordenar == 'preco_asc' %}selected{% endif %}>Preço: Baixo → Alto</option>
              <option value="preco_desc" {% if ordenar == 'preco_desc' %}selected{% endif %}>Preço: Alto → Baixo</option>
              <option value="distancia" {% if ordenar == 'distancia' %}selected{% endif %}>Distância à faculdade</option>
              <option value="seguranca" {% if ordenar == 'seguranca' %}selected{% endif %}>Segurança (melhor)</option>
              <option value="ruido_asc" {% if ordenar == 'ruido_asc' %}selected{% endif %}>Mais tranquilo</option>
              <option value="comercio" {% if ordenar == 'comercio' %}selected{% endif %}>Mais comércio</option>
            </select>
          </div>
        </div>
        <div class="row g-3 mt-0 align-items-center">
          <div class="col-md-3">
            <label class="form-label small d-flex justify-content-between">
              <span>Segurança mín.</span><span id="seg-val" class="slider-val">{{ seg_min or 0 }}</span>
            </label>
            <input type="range" id="seguranca_min" name="seg_min" class="form-range" min="0" max="10" step="1" value="{{ seg_min or 0 }}">
          </div>
          <div class="col-md-3">
            <label class="form-label small d-flex justify-content-between" title="Quanto mais alto, menos ruído">
              <span>Ruído mín.</span><span id="tra-val" class="slider-val">{{ tranquilo_min if tranquilo_min is not none else 0 }}</span>
            </label>
            <input type="range" id="tranquilo_min" name="tranquilo_min" class="form-range" min="0" max="10" step="1" value="{{ tranquilo_min if tranquilo_min is not none else 0 }}">
          </div>
          <div class="col-md-3">
            <label class="form-label small d-flex justify-content-between">
              <span>Comércio mín.</span><span id="com-val" class="slider-val">{{ com_min or 0 }}</span>
            </label>
            <input type="range" id="comercio_min" name="com_min" class="form-range" min="0" max="10" step="1" value="{{ com_min or 0 }}">
          </div>
          <div class="col-md-3 d-grid">
            <button type="submit" class="btn btn-laranja btn-sm py-2">🔍 Filtrar</button>
          </div>
        </div>
      </form>
    </div>
  </div>

  <!-- Legenda de fontes -->
  <div class="fontes-legend mb-3">
    <span><span class="dot" style="background:#ecc94b"></span>Imovirtual</span>
    <span class="ms-3"><span class="dot" style="background:#e53e3e"></span>OLX</span>
    <span class="ms-3"><span class="dot" style="background:#4299e1"></span>CustoJusto</span>
    <span class="ms-3"><span class="dot" style="background:#2f855a"></span>Idealista</span>
  </div>

  {% if anuncios %}
  <div class="row g-4">
    {% for a in anuncios %}
    <div class="col-sm-6 col-lg-4 col-xl-3">
      <div class="card card-ad h-100">
        <div style="position:relative;">
          {% if a.imagem %}
          <img src="{{ a.imagem }}" class="ad-img" alt="Foto" onerror="this.outerHTML='<div class=&quot;ad-img-ph&quot;>🏠</div>'">
          {% else %}
          <div class="ad-img-ph"><span style="font-size:2rem">🏠</span></div>
          {% endif %}
          <span class="badge-fonte" style="background:{{ fonte_cores[a.fonte] }}">{{ a.fonte }}</span>
          <span class="badge-data">{{ a.data }}</span>
        </div>
        <div class="card-body d-flex flex-column" style="padding:.85rem;">
          <h6 class="ad-titulo">{{ a.titulo }}</h6>
          <div class="ad-preco">{{ '%.0f' % a.preco }} € <small>/ mês</small></div>
          {% if a.disponibilidade %}
          <span class="badge text-bg-success mt-1 align-self-start">{{ a.disponibilidade }}</span>
          {% endif %}
          <div class="d-flex gap-2 mt-1 flex-wrap">
            <span class="badge badge-zona">📍 {{ a.zona or 'Zona não identificada' }}</span>
            {% if a.distancia is not none %}
            <span class="badge text-bg-info dist-badge">🚶 {{ a.distancia }} km</span>
            {% endif %}
          </div>
          {% if a.distancia is not none %}
          <div class="dist-box mt-2">Distância a {{ faculdade or 'faculdade' }}: {{ a.distancia }} km <span style="font-weight:500;opacity:.75">(linha reta)</span></div>
          {% endif %}
          <p class="ad-desc mt-2 mb-0">{{ a.descricao }}</p>
          {% if a.zona %}
          <div class="zona-notas mt-3">
            <div class="notas-icones">
              <span class="nota-icone" title="Segurança"><i>🛡️</i>
                <span class="{{ badge_nota(a.seguranca) }}">{{ a.seguranca if a.seguranca is not none else '—' }}/10</span></span>
              <span class="nota-icone" title="Ruído (mais alto = mais sossegado)"><i>🤫</i>
                <span class="{{ badge_nota(a.tranquilo) }}">{{ a.tranquilo if a.tranquilo is not none else '—' }}/10</span></span>
              <span class="nota-icone" title="Comércio"><i>🛒</i>
                <span class="{{ badge_nota(a.comercio) }}">{{ a.comercio if a.comercio is not none else '—' }}/10</span></span>
            </div>
            <div class="transporte-grid mt-2">
              {% if a.metro_min is not none %}<span>Metro {{ a.metro_min }}m</span>{% endif %}
              {% if a.bus_min is not none %}<span>Bus {{ a.bus_min }}m</span>{% endif %}
              {% if a.comboio_min is not none %}<span>Comboio {{ a.comboio_min }}m</span>{% endif %}
            </div>
          </div>
          {% endif %}
          <div class="mt-auto pt-3">
            <a href="{{ a.link }}" target="_blank" rel="noopener" class="btn btn-laranja btn-sm w-100">🔗 Ver Anúncio Original</a>
          </div>
        </div>
      </div>
    </div>
    {% endfor %}
  </div>
  {% else %}
  <div class="text-center py-5 placeholder-msg">
    <p style="font-size:3rem">🔍</p>
    <h5>Nenhum anúncio corresponde aos filtros.</h5>
    <a href="{{ url_for('refresh', cidade=cidade) }}" class="btn btn-outline-primary mt-2">Atualizar agora</a>
  </div>
  {% endif %}

</div>

<footer class="text-center py-4">
  Aloja-Te — Encontra quarto sem complicações — Porto | Lisboa | Coimbra<br>
  <span class="fontes-legend">Fontes: Imovirtual · OLX · CustoJusto{% if fonte_idealista %} · Idealista{% endif %} · Distâncias em linha reta (Haversine)</span>
</footer>

<script>
document.addEventListener('DOMContentLoaded', () => {
  const cidadeSel = document.getElementById('cidade');
  const facSel = document.getElementById('faculdade');
  const form = document.getElementById('filtros');

  // mostra só as universidades da cidade selecionada
  function filtrarFaculdades() {
    const cidade = cidadeSel.value;
    const o = facSel.selectedOptions[0];
    if (o && o.dataset.cidade && o.dataset.cidade !== cidade) facSel.value = '';
    facSel.querySelectorAll('optgroup').forEach(g => {
      g.style.display = g.getAttribute('label') === cidade ? '' : 'none';
    });
  }

  cidadeSel.addEventListener('change', () => {
    filtrarFaculdades();
    form.submit();
  });

  facSel.addEventListener('change', () => form.submit());

  filtrarFaculdades();

  const bind = (id, saida) => {
    const el = document.getElementById(id);
    el.addEventListener('input', () => document.getElementById(saida).textContent = el.value);
  };
  bind('seguranca_min', 'seg-val');
  bind('tranquilo_min', 'tra-val');
  bind('comercio_min', 'com-val');
});
</script>
</body>
</html>
"""

FONTE_CORES = {"Imovirtual": "#ecc94b", "OLX": "#e53e3e", "CustoJusto": "#4299e1",
               "Idealista": "#2f855a"}


@app.after_request
def _no_cache(resp):
    """Evita que o browser guarde versões antigas da página (resultados sempre atuais)."""
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.route("/")
def index():
    cidade = _slug_cidade(request.args.get("cidade", "Porto"))
    faculdade = (request.args.get("faculdade") or "").strip()
    # se escolheu uma universidade, a cidade segue-a (dropdown global)
    if faculdade:
        fcity = _cidade_da_faculdade(faculdade)
        if fcity:
            cidade = fcity
    preco_min = _float(request.args.get("preco_min"))
    preco_max = _float(request.args.get("preco_max"))
    dist_max = _float(request.args.get("dist_max"))
    # ordenação por defeito: preço (baixo → alto). '' = "Mais recentes"
    ordenar_raw = request.args.get("ordenar")
    ordenar = ordenar_raw if ordenar_raw is not None else "preco_asc"
    ordenar = ordenar.strip()
    seg_min = _int(request.args.get("seg_min"))
    tranquilo_min = _int(request.args.get("tranquilo_min"))
    com_min = _int(request.args.get("com_min"))
    # profundidade de pesquisa: 1..5 páginas por fonte (defeito 2)
    paginas = max(1, min(_int(request.args.get("paginas")) or 2, 5))

    anuncios, fontes, ts = carregar_anuncios(cidade, paginas)
    anuncios = _aplicar_filtros(anuncios, cidade, faculdade, preco_min, preco_max,
                                dist_max, seg_min, tranquilo_min, com_min)
    _ordenar(anuncios, ordenar, faculdade, cidade)
    anuncios = _balanceado(anuncios, MAX_TOTAL)
    _ordenar(anuncios, ordenar, faculdade, cidade)

    for a in anuncios:
        a["descricao"] = a["descricao"][:140] + ("…" if len(a["descricao"]) > 140 else "")

    if not fontes:
        alerta = {"classe": "alert-warning",
                  "texto": "Não foi possível carregar dados reais das fontes.",
                  "acao": "Tentar novamente",
                  "link": url_for("refresh", cidade=cidade, paginas=paginas)}
    else:
        alerta = {"classe": "alert-info",
                  "texto": "Fontes ativas: %s" % (" + ".join(fontes) if fontes else "nenhuma"),
                  "acao": "Atualizar agora",
                  "link": url_for("refresh", cidade=cidade, paginas=paginas)}

    if not anuncios:
        alerta = {"classe": "alert-warning",
                  "texto": "Nenhum anúncio disponível para esta pesquisa.",
                  "acao": "Tentar novamente",
                  "link": url_for("refresh", cidade=cidade, paginas=paginas)}

    agora = datetime.fromtimestamp(ts)
    return render_template_string(
        HTML_TEMPLATE,
        cidades=CIDADES,
        cidades_extra=CIDADES_EXTRA,
        universidades_grupos=UNIVERSIDADES_GRUPOS,
        cidade=cidade,
        faculdade=faculdade,
        preco_min=preco_min, preco_max=preco_max, dist_max=dist_max,
        ordenar=ordenar, seg_min=seg_min, tranquilo_min=tranquilo_min, com_min=com_min,
        paginas=paginas,
        anuncios=anuncios, total=len(anuncios),
        fonte_cores=FONTE_CORES, alerta=alerta, fonte_idealista=("Idealista" in fontes),
        cache_min=CACHE_TTL // 60,
        atualizado=agora.strftime("%H:%M:%S"),
        estrelas_html=estrelas_html, badge_nota=badge_nota,
    )


@app.route("/refresh")
def refresh():
    cidade = _slug_cidade(request.args.get("cidade", "Porto"))
    paginas = request.args.get("paginas")
    if paginas:
        invalidar_cache(cidade, max(1, min(_int(paginas) or 2, 5)))
    else:
        invalidar_cache(cidade)
    return redirect(url_for("index", cidade=cidade, paginas=paginas or 2))


@app.route("/api/anuncios")
def api_anuncios():
    cidade = _slug_cidade(request.args.get("cidade", "Porto"))
    faculdade = (request.args.get("faculdade") or "").strip()
    ordenar = (request.args.get("ordenar") or "preco_asc").strip()
    paginas = max(1, min(_int(request.args.get("paginas")) or 2, 5))
    anuncios, fontes, _ts = carregar_anuncios(cidade, paginas)
    anuncios = _aplicar_filtros(anuncios, cidade, faculdade,
                                _float(request.args.get("preco_min")),
                                _float(request.args.get("preco_max")),
                                _float(request.args.get("dist_max")),
                                _int(request.args.get("seg_min")),
                                _int(request.args.get("tranquilo_min")),
                                _int(request.args.get("com_min")))
    _ordenar(anuncios, ordenar, faculdade, cidade)
    anuncios = _balanceado(anuncios, MAX_TOTAL)
    _ordenar(anuncios, ordenar, faculdade, cidade)
    for a in anuncios:
        a["distancia"] = calcular_distancia_faculdade(a["lat"], a["lon"], faculdade, cidade)
    return jsonify({"cidade": cidade, "fontes": fontes, "paginas": paginas,
                    "total": len(anuncios), "anuncios": anuncios})


@app.route("/api/faculdades")
def api_faculdades():
    cidade = _slug_cidade(request.args.get("cidade", "Porto"))
    return jsonify({"cidade": cidade, "faculdades": FACULDADES.get(cidade, [])})


if __name__ == "__main__":
    print("Aloja-Te a correr em http://127.0.0.1:%d" % PORT)
    app.run(host="0.0.0.0", port=PORT, debug=False)
