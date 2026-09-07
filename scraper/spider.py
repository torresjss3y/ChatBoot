import scrapy
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

class SitioPhpSpider(CrawlSpider):
    name = "sitio_php"

    allowed_domains = ["ucss.edu.pe", "www.ucss.edu.pe"]
    start_urls = ["https://www.ucss.edu.pe/"]

    # Ignorar archivos binarios, imágenes, documentos y comprimidos
    rules = (
        Rule(
            LinkExtractor(
                deny_extensions=[
                    'pdf', 'docx', 'doc', 'xlsx', 'xls', 'ppt', 'pptx',
                    'zip', 'rar', 'gz', 'tar',
                    'png', 'jpg', 'jpeg', 'gif', 'svg', 'mp4', 'mp3'
                ]
            ), 
            callback="parse_page", 
            follow=True
        ),
    )

    custom_settings = {
        "USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "DOWNLOAD_DELAY": 0.2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 16,
    }

    def parse_page(self, response):
        # Asegurarse de que la respuesta sea HTML y no otro tipo de archivo
        if "text/html" not in response.headers.get("Content-Type", b"").decode("utf-8"):
            return

        parrafos = response.css("p::text").getall()
        texto_limpio = " ".join([p.strip() for p in parrafos if p.strip()])

        encabezados_raw = response.css("h1::text, h2::text, h3::text").getall()
        encabezados = [h.strip() for h in encabezados_raw if h.strip()]

        yield {
            "url": response.url,
            "titulo": response.css("title::text").get(default="").strip(),
            "encabezados": encabezados,
            "contenido_texto": texto_limpio,
        }