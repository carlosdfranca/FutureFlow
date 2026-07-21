"""
Script de teste para validar parser de XML NF-e com o arquivo fornecido.
Execute: python test_parser_xml.py
"""
import sys
import os
from pathlib import Path

# Adicionar o diretório do projeto ao path
sys.path.insert(0, str(Path(__file__).parent))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fidc_gestao.settings')
import django
django.setup()

from core.services.cessao_xml import parse_nfe_xml

# Caminho para o XML de exemplo
XML_PATH = r"c:\Users\carlo\OneDrive\Trampo\Projetos\Cinnamon\Future Flow\CNAB\Exemplo Import CNAB.xml"

def test_parser():
    print("=" * 80)
    print("TESTE DO PARSER DE XML NF-e")
    print("=" * 80)
    
    # Ler o arquivo XML
    with open(XML_PATH, 'rb') as f:
        xml_bytes = f.read()
    
    # Parse
    try:
        result = parse_nfe_xml(xml_bytes)
        
        print("\n✓ XML parseado com sucesso!\n")
        
        print("--- DADOS DO CEDENTE ---")
        print(f"Nome: {result.partes.cedente_nome}")
        print(f"CNPJ: {result.partes.cedente_doc}")
        print(f"Endereço: {result.partes.cedente_endereco}")
        
        print("\n--- DADOS DO SACADO ---")
        print(f"Nome: {result.partes.sacado_nome}")
        print(f"CNPJ: {result.partes.sacado_doc}")
        
        print("\n--- DADOS DA NF ---")
        print(f"Número NF: {result.partes.numero_nota}")
        print(f"Data Emissão: {result.partes.data_emissao_iso}")
        
        print("\n--- TÍTULOS ENCONTRADOS ---")
        print(f"Quantidade: {len(result.titulos)}")
        for i, titulo in enumerate(result.titulos, 1):
            print(f"\nTítulo {i}:")
            print(f"  Número: {titulo.numero_titulo}")
            print(f"  Sacado: {titulo.sacado_nome}")
            print(f"  Valor: R$ {titulo.valor:,.2f}")
            print(f"  Vencimento: {titulo.vencimento_iso}")
            print(f"  Tipo: {titulo.tipo_credito}")
            print(f"  Endereço Sacado: {titulo.sacado_endereco}")
            print(f"  CEP Sacado: {titulo.sacado_cep}")
            print(f"  Chave NF-e: {titulo.chave_nfe}")
            print(f"  Data Emissão (título): {titulo.data_emissao_iso}")
        
        print(f"\n--- TOTAL ---")
        print(f"Valor Total: R$ {result.total:,.2f}")
        
        print("\n" + "=" * 80)
        print("✓ TESTE CONCLUÍDO COM SUCESSO!")
        print("=" * 80)
        
        # Validações esperadas
        assert result.partes.cedente_doc == "02455462000129", "CNPJ do cedente incorreto"
        assert result.partes.cedente_nome == "PROTURBO USINAGEM DE PRECISAO LTDA.", "Nome do cedente incorreto"
        assert result.partes.sacado_doc == "57010662001212", "CNPJ do sacado incorreto"
        assert result.partes.numero_nota == "154586", "Número da NF incorreto"
        assert len(result.titulos) == 1, "Deveria ter 1 duplicata"
        assert result.titulos[0].numero_titulo == "001", "Número da duplicata incorreto"
        assert result.titulos[0].vencimento_iso == "2026-07-10", "Vencimento incorreto"
        assert result.titulos[0].valor == 80911.50, "Valor da duplicata incorreto"
        assert "AV DAS INDUSTRIAS" in result.partes.cedente_endereco, "Endereço do cedente não foi extraído"
        assert "ROD SANTOS DUMONT" in result.titulos[0].sacado_endereco, "Endereço do sacado não foi extraído"
        assert result.titulos[0].sacado_cep == "13012100", "CEP do sacado incorreto"
        assert result.titulos[0].chave_nfe == "35260502455462000129550010001545861100956966", "Chave NF-e incorreta"
        assert result.titulos[0].data_emissao_iso == "2026-05-11", "Data de emissão do título incorreta (deve vir sem componente de hora)"
        
        print("\n✓ Todas as validações passaram!")
        
    except Exception as e:
        print(f"\n✗ ERRO ao parsear XML: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = test_parser()
    sys.exit(0 if success else 1)
