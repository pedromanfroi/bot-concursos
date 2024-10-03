import requests
from bs4 import BeautifulSoup

def fetch_cargos(url):
    """
    Faz uma requisição para a URL fornecida e extrai os cargos dos concursos.
    
    Args:
        url (str): URL da página de concursos.
    
    Returns:
        set: Conjunto de cargos únicos encontrados na página.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()  # Verifica se a requisição foi bem-sucedida
    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar a página: {e}")
        return set()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    cargos_set = set()
    
    # Encontrar todas as divs com classe 'na' que contêm os concursos
    concursos = soup.find_all('div', class_='na')
    
    for concurso in concursos:
        # Encontrar a div com classe 'cd' que contém as vagas e cargos
        cd_div = concurso.find('div', class_='cd')
        if cd_div:
            # Dentro de 'cd', encontrar todos os spans
            spans = cd_div.find_all('span')
            if len(spans) >= 1:
                # O primeiro span contém as posições (cargos)
                posicoes_text = spans[0].get_text(separator=', ').strip()
                # Dividir os cargos por vírgula e adicionar ao conjunto
                posicoes = [cargo.strip() for cargo in posicoes_text.split(',')]
                cargos_set.update(posicoes)
    
    return cargos_set

def main():
    url = 'https://www.pciconcursos.com.br/concursos/sul/'
    cargos = fetch_cargos(url)
    
    if cargos:
        print(f"Total de cargos encontrados: {len(cargos)}\n")
        print("Lista de Cargos:")
        for idx, cargo in enumerate(sorted(cargos), 1):
            print(f"{idx}. {cargo}")
    else:
        print("Nenhum cargo encontrado.")

if __name__ == "__main__":
    main()
