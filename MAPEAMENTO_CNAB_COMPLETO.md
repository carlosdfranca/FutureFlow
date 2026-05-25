# 📊 Mapeamento Completo: XML → CNAB (Baseado no VBA Real)

**Data**: 25/05/2026  
**Fonte**: Análise do código VBA + Resultado real do Excel

---

## ✅ Campos Confirmados que PRECISAMOS Extrair

| # | Coluna CNAB | Valor Exemplo | Origem XML | Status Python |
|---|-------------|---------------|------------|---------------|
| 1 | CNPJ_CEDENTE | 02455462000129 | `//emit/CNPJ` | ✅ Extraído |
| 2 | NOME_CEDENTE | PROTURBO USINAGEM... | `//emit/xNome` | ✅ Extraído |
| 3 | SEU_NUMERO | 10000001 | Gerado (sequencial) | ⚠️ Lógica app |
| 4 | NU_DOCUMENTO | 586/002 | `//cobr/fat/nFat` + sufixo | ⚠️ Ver nota¹ |
| 5 | DT_VENCIMENTO | 26/04/2022 | **MANUAL** (não XML) | ⚠️ Editável |
| 6 | VL_NOMINAL | 80911,50 | `//cobr/dup/vDup` | ✅ Extraído |
| 7 | NU_CPF_CNPJ_SACADO | 57010662001212 | `//dest/CNPJ` | ✅ Extraído |
| 8 | NM_SACADO | VALEO... (40 chars) | `//dest/xNome` | ✅ Extraído |
| 9 | VL_PAGO | 17942,43 | **MANUAL** (não XML) | ⚠️ Não aplicável |
| 10 | IDENTIFICACAO_SACADO | 02 | Código fixo (PJ) | ⚠️ Lógica app |
| 11 | **ENDEREÇO_SACADO** | ROD SANTOS DUMONT KM | `//dest/enderDest/xLgr` | ❌ **FALTA!** |
| 12 | **CEP_SACADO** | 13012100 | `//dest/enderDest/CEP` | ❌ **FALTA!** |
| 13 | TP_TITULO | 01 | Código fixo (Duplicata) | ⚠️ Lógica app |
| 14 | DT_EMISSAO | 11/05/2026 | `//ide/dhEmi` | ✅ Extraído |
| 15 | COOBRIGACAO | 2 | Código fixo | ⚠️ Lógica app |
| 16 | IDENTIFICACAO_CEDENTE | 2 | Código fixo (PJ) | ⚠️ Lógica app |
| 17 | **CHAVE_NFE** | 3526050245... | `//infProt/chNFe` | ❌ **FALTA!** |
| 18 | VALOR_PAGO_TITULO | (vazio) | Calculado depois | ⚠️ Não aplicável |

---

## 🚨 Confirmação do XML Real

### Endereço do Sacado (DESTINATÁRIO)
```xml
<enderDest>
    <xLgr>ROD SANTOS DUMONT KM 64</xLgr>
    <nro>S/N</nro>
    <xCpl>Qt30036 -L05</xCpl>
    <xBairro>HELVETIA</xBairro>
    <cMun>3509502</cMun>
    <xMun>CAMPINAS</xMun>
    <UF>SP</UF>
    <CEP>13012100</CEP>
</enderDest>
```

**Resultado esperado**: `ROD SANTOS DUMONT KM` (truncado em 40 caracteres para CNAB)

### Chave da NF-e
```xml
<infProt>
    <chNFe>35260502455462000129550010001545861100956966</chNFe>
</infProt>
```

**Resultado esperado**: `35260502455462000129550010001545861100956966` (44 dígitos)

### Número da Fatura
```xml
<fat>
    <nFat>154586</nFat>
</fat>
```

**Nota¹**: O resultado mostra "586/002", mas o XML tem "154586". Possíveis explicações:
- Formatação da célula do Excel
- XML usado para gerar o resultado era diferente
- Lógica de truncamento no VBA

---

## 🎯 Campos CRÍTICOS que Faltam

### ❌ 1. Endereço do Sacado
**Impacto**: CNAB posição 11 (40 caracteres)  
**Extração**: `dest/enderDest/xLgr`  
**Uso**: Identificação do sacado no arquivo de remessa

### ❌ 2. CEP do Sacado
**Impacto**: CNAB posição 12  
**Extração**: `dest/enderDest/CEP`  
**Uso**: Dados cadastrais do sacado

### ❌ 3. Chave da NF-e
**Impacto**: CNAB posição 17 (44 dígitos)  
**Extração**: `infProt/chNFe`  
**Uso**: Rastreabilidade, validação SEFAZ, compliance

---

## 🔧 Alterações Necessárias

### 1. Atualizar Model `Titulo`
```python
class Titulo(models.Model):
    # ... campos existentes ...
    
    # NOVOS CAMPOS NECESSÁRIOS:
    sacado_endereco = models.CharField(max_length=200, blank=True)
    sacado_cep = models.CharField(max_length=8, blank=True)
    chave_nfe = models.CharField(max_length=44, blank=True, 
                                  help_text="Chave de acesso da NF-e (44 dígitos)")
```

### 2. Atualizar Parser XML
```python
# Extrair endereço do SACADO (destinatário)
sacado_endereco = ""
sacado_cep = ""
ender_dest = _safe_find(dest, "enderDest", ns)
if ender_dest is not None:
    lgr = _safe_find_text(ender_dest, "xLgr", ns)
    nro = _safe_find_text(ender_dest, "nro", ns)
    cep = _safe_find_text(ender_dest, "CEP", ns)
    
    if lgr:
        sacado_endereco = f"{lgr}"
        if nro and nro != "S/N":
            sacado_endereco += f" {nro}"
    sacado_cep = cep

# Extrair chave da NF-e
chave_nfe = ""
inf_prot = root.find(".//infProt", namespaces)
if inf_prot is not None:
    chave_nfe = _safe_find_text(inf_prot, "chNFe", ns)
```

### 3. Atualizar Dataclass `TituloCessao`
```python
@dataclass(frozen=True)
class TituloCessao:
    sacado_nome: str
    sacado_doc: str
    valor: Decimal
    vencimento_iso: str
    tipo_credito: str = "Duplicata"
    numero_titulo: str = ""
    sacado_endereco: str = ""  # NOVO
    sacado_cep: str = ""       # NOVO
    chave_nfe: str = ""        # NOVO
```

---

## ⚠️ Notas Importantes

### Dados Manuais (NÃO vêm do XML)
1. **DT_VENCIMENTO**: No Excel mostra "26/04/2022", mas no XML é "2026-07-10"
   - Confirmação: Campo MENU.B7 (entrada manual do usuário)
   - No nosso sistema: Usar vencimento do XML como padrão, permitir edição

2. **VL_PAGO**: Mostra "17942,43" mas não está no XML
   - Confirmação: Campo MENU.B8 (entrada manual)
   - No nosso sistema: Não aplicável no momento do import

3. **SEU_NUMERO**: "10000001" é sequencial gerado pelo VBA
   - No nosso sistema: Podemos usar ID da operação ou gerar sequencial

### Códigos CNAB Fixos
- **IDENTIFICACAO_CPF_CNPJ_SACADO**: "02" (PJ)
- **IDENTIFICACAO_CPF_CNPJ_CEDENTE**: "02" (PJ)
- **TP_TITULO**: "01" (Duplicata)
- **COOBRIGACAO**: "2" (Sem coobrigação)

**Estes códigos devem ser gerados na hora de criar o arquivo CNAB**, não precisam estar no parser XML.

---

## ✅ Próximos Passos

1. ✅ Criar migration para adicionar campos ao model `Titulo`
2. ✅ Atualizar parser XML para extrair endereço sacado + CEP + chave NFe
3. ✅ Atualizar formulários para aceitar novos campos
4. ✅ Testar com XML fornecido
5. ⏳ Implementar geração CNAB (Fase 8) usando esses dados
