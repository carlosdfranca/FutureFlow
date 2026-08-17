from django.test import TestCase

from core.services.cessao_xml import parse_nfe_xml


def _nfe_xml(
    numero_nota="155771",
    n_fat="155771",
    dups=(("001", "2026-08-14", "21448.80"),),
    dh_emi="2026-06-15T00:00:00-03:00",
    chave="35260602455462000129550010001557711769163725",
    ender_emit=None,
    ender_dest=None,
):
    """Monta um XML de NF-e mínimo (mesma estrutura nfeProc + protNFe dos
    arquivos reais) para testar a extração de numero_titulo isoladamente.

    ender_emit / ender_dest: dict opcional com chaves xLgr/nro/xCpl/xBairro/xMun/UF/CEP
    (enderEmit) ou xLgr/nro/CEP (enderDest) — só entra no XML se fornecido, pra não
    alterar o comportamento dos testes que não se importam com endereço.
    """
    dup_xml = "".join(
        f"<dup><nDup>{n_dup}</nDup><dVenc>{d_venc}</dVenc><vDup>{v_dup}</vDup></dup>"
        for n_dup, d_venc, v_dup in dups
    )

    def _ender_xml(tag, campos):
        if not campos:
            return ""
        corpo = "".join(f"<{k}>{v}</{k}>" for k, v in campos.items())
        return f"<{tag}>{corpo}</{tag}>"

    ender_emit_xml = _ender_xml("enderEmit", ender_emit)
    ender_dest_xml = _ender_xml("enderDest", ender_dest)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe xmlns="http://www.portalfiscal.inf.br/nfe">
    <infNFe Id="NFe{chave}" versao="4.00">
      <ide><nNF>{numero_nota}</nNF><dhEmi>{dh_emi}</dhEmi></ide>
      <emit><CNPJ>02455462000129</CNPJ><xNome>CEDENTE TESTE LTDA</xNome>{ender_emit_xml}</emit>
      <dest><CNPJ>43201151000110</CNPJ><xNome>SACADO TESTE LTDA</xNome>{ender_dest_xml}</dest>
      <cobr><fat><nFat>{n_fat}</nFat></fat>{dup_xml}</cobr>
    </infNFe>
  </NFe>
  <protNFe versao="4.00">
    <infProt><chNFe>{chave}</chNFe></infProt>
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


class ParseNfeXmlCamposComplementaresTest(TestCase):
    """
    Cobre endereço/CEP do cedente e do sacado, chave de acesso da NF-e e a
    data de emissão sem componente de hora — validações que antes só existiam
    no script manual test_parser_xml.py (removido; dependia de um XML fora do
    repo, em caminho absoluto do OneDrive de um único desenvolvedor).
    """

    def test_extrai_endereco_do_cedente(self):
        xml = _nfe_xml(ender_emit={
            "xLgr": "AV DAS INDUSTRIAS", "nro": "1000", "xBairro": "DISTRITO INDUSTRIAL",
            "xMun": "MANAUS", "UF": "AM", "CEP": "69000000",
        })
        result = parse_nfe_xml(xml)
        self.assertIn("AV DAS INDUSTRIAS", result.partes.cedente_endereco)

    def test_extrai_endereco_e_cep_do_sacado(self):
        xml = _nfe_xml(ender_dest={
            "xLgr": "ROD SANTOS DUMONT", "nro": "500", "CEP": "13012100",
        })
        result = parse_nfe_xml(xml)
        self.assertIn("ROD SANTOS DUMONT", result.titulos[0].sacado_endereco)
        self.assertEqual(result.titulos[0].sacado_cep, "13012100")

    def test_extrai_chave_nfe_do_protnfe(self):
        xml = _nfe_xml(chave="35260502455462000129550010001545861100956966")
        result = parse_nfe_xml(xml)
        self.assertEqual(result.titulos[0].chave_nfe, "35260502455462000129550010001545861100956966")

    def test_data_emissao_iso_sem_componente_hora(self):
        xml = _nfe_xml(dh_emi="2026-05-11T10:23:00-03:00")
        result = parse_nfe_xml(xml)
        self.assertEqual(result.titulos[0].data_emissao_iso, "2026-05-11")
