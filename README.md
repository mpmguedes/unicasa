# UniCasa - Busca Inteligente para Estudantes

Agregador de quartos para estudantes em Portugal. Dados reais do Imovirtual com filtros por faculdade, preço, qualidade da zona e distância.

## Cidades suportadas
- **Porto** (17 faculdades, 16 zonas)
- **Lisboa** (16 faculdades, 17 zonas)
- **Coimbra** (12 faculdades, 10 zonas)

## Funcionalidades
- Scraping de anúncios reais do Imovirtual (até 3 páginas = ~110 anúncios/cidade)
- Cálculo de distância à faculdade (fórmula de Haversine)
- Classificação de zonas: Segurança, Ruído, Comércio, Transportes
- Filtros: Preço, Distância, Segurança mínima, Ruído máximo, Comércio mínimo
- Ordenação: Preço, Distância, Segurança, Ruído, Comércio
- Cache de 15 minutos

## Instalação

```bash
# 1. Clonar o repositório
git clone https://github.com/SEU_USER/unicasa.git
cd unicasa

# 2. Criar ambiente virtual
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Executar
python app.py

# 5. Abrir no browser
# http://127.0.0.1:5000
```

## Estrutura do projeto
```
unicasa/
├── app.py              # Aplicação Flask principal
├── requirements.txt    # Dependências Python
├── README.md           # Este ficheiro
└── .gitignore          # Ficheiros ignorados pelo git
```

## Tecnologias
- **Flask** — servidor web
- **BeautifulSoup + lxml** — parsing HTML
- **requests** — HTTP requests
- **geopy + Nominatim** — geocodificação
- **feedparser** — feeds RSS (fallback)

## Dados
- Faculdades: coordenadas reais (lat/lon)
- Zonas: classificações baseadas em pesquisa (0-10)
- Anúncios: extraídos em tempo real do Imovirtual.pt

## Limitações
- Idealista e OLX têm proteção anti-bot (Cloudflare/CAPTCHA) e não são acessíveis via scraping
- Geocodificação usa Nominatim (OpenStreetMap) com fallback por zona

## Futuro
- Playwright/Selenium para contornar proteções do Idealista/OLX
- Paginação para mais anúncios por cidade
- Base de dados para persistência
- Deploy em VPS/cloud

## Licença
MIT
