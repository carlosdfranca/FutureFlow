from django.test import TestCase

from core.services.cessao_xml import parse_nfe_xml


def _nfe_xml(numero_nota="155771", n_fat="155771", dups=(("001", "2026-08-14", "21448.80"),)):
    """Monta um XML de NF-e mínimo (mesma estrutura nfeProc + protNFe dos
    arquivos reais) para testar a extração de numero_titulo isoladamente."""
    dup_xml = "".join(
        f"<dup><nDup>{n_dup}</nDup><dVenc>{d_venc}</dVenc><vDup>{v_dup}</vDup></dup>"
        for n_dup, d_venc, v_dup in dups
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe xmlns="http://www.portalfiscal.inf.br/nfe">
    <infNFe Id="NFe35260602455462000129550010001557711769163725" versao="4.00">
      <ide><nNF>{numero_nota}</nNF><dhEmi>2026-06-15T00:00:00-03:00</dhEmi></ide>
      <emit><CNPJ>02455462000129</CNPJ><xNome>CEDENTE TESTE LTDA</xNome></emit>
      <dest><CNPJ>43201151000110</CNPJ><xNome>SACADO TESTE LTDA</xNome></dest>
      <cobr><fat><nFat>{n_fat}</nFat></fat>{dup_xml}</cobr>
    </infNFe>
  </NFe>
  <protNFe versao="4.00">
    <infProt><chNFe>35260602455462000129550010001557711769163725</chNFe></infProt>
  </protNFe>
</nfeProc>""".encode("utf-8")


class ParseNfeXmlNumeroTituloTest(TestCase):
    """
    numero_titulo (SEU_NUMERO/NU_DOCUMENTO no CNAB) deve vir de cobr/fat/nFat
    (número da fatura), como a macro Módulo3.bas faz — não de cobr/dup/nDup
    (número da parcela), que se repetiria ("001") em toda nota com parcela
    única. Ver docs/plano_implementacao_cobranca.md.
    """

    def test_parcela_unica_usa_nfat(self):
        xml = _nfe_xml(n_fat="155771", dups=(("001", "2026-08-14", "21448.80"),))
        result = parse_nfe_xml(xml)
        self.assertEqual(len(result.titulos), 1)
        self.assertEqual(result.titulos[0].numero_titulo, "155771")

    def test_multiplas_parcelas_mantem_numero_titulo_unico_por_parcela(self):
        xml = _nfe_xml(n_fat="155771", dups=(
            ("001", "2026-08-14", "10000.00"),
            ("002", "2026-09-14", "10000.00"),
        ))
        result = parse_nfe_xml(xml)
        self.assertEqual(len(result.titulos), 2)
        self.assertEqual(result.titulos[0].numero_titulo, "155771-001")
        self.assertEqual(result.titulos[1].numero_titulo, "155771-002")
        # Continuam distintos entre si — nenhum SEU_NUMERO duplicado no lote.
        self.assertNotEqual(result.titulos[0].numero_titulo, result.titulos[1].numero_titulo)

    def test_sem_nfat_cai_no_numero_da_nota(self):
        xml = _nfe_xml(numero_nota="999999", n_fat="", dups=(("001", "2026-08-14", "500.00"),))
        result = parse_nfe_xml(xml)
        self.assertEqual(result.titulos[0].numero_titulo, "999999")

    def test_sem_duplicata_usa_nfat(self):
        xml = _nfe_xml(n_fat="155771", dups=())
        result = parse_nfe_xml(xml)
        self.assertEqual(len(result.titulos), 1)
        self.assertEqual(result.titulos[0].numero_titulo, "155771")
