# 🔍 Comparação: VBA vs Python - Parser XML NF-e

**Data**: 25/05/2026  
**Objetivo**: Verificar se nosso parser Python extrai TODOS os dados que o VBA extrai

---

## 📊 Análise do Código VBA

### Dados Extraídos pelo VBA

| Coluna | Campo | XPath VBA | Status Python |
|--------|-------|-----------|---------------|
| A (1) | CNPJ Emitente | `//emit/CNPJ` | ✅ Extraído |
| B (2) | Nome Emitente | `//emit/xNome` | ✅ Extraído |
| C (3) | Número Sequencial | Gerado automaticamente | ⚠️ Não aplicável |
| D (4) | Número Fatura + Sufixo | `//cobr/fat/nFat` & "/001" | ❌ **DIFERENTE** |
| E (5) | Vencimento | Manual (MENU.B7) | ⚠️ Nosso usa `//cobr/dup/dVenc` |
| F (6) | Valor Duplicata | `//cobr/dup/vDup` | ✅ Extraído |
| G (7) | CNPJ Destinatário | `//dest/CNPJ` | ✅ Extraído |
| H (8) | Nome Destinatário | `//dest/xNome` | ✅ Extraído |
| I (9) | Valor Manual | MENU.B8 | ⚠️ Não aplicável |
| J (10) | Código Fixo | "02" | ⚠️ Código CNAB |
| K (11) | Endereço Destinatário | `//dest/enderDest/xLgr` | ❌ **NÃO EXTRAÍDO** |
| L (12) | CEP Destinatário | `//dest/enderDest/CEP` | ❌ **NÃO EXTRAÍDO** |
| M (13) | Código Fixo | "01" | ⚠️ Código CNAB |
| N (14) | Data Emissão | `//ide/dhEmi` | ✅ Extraído |
| O (15) | Código Fixo | "02" | ⚠️ Código CNAB |
| P (16) | Código Fixo | "02" | ⚠️ Código CNAB |
| Q (17) | Chave NF-e | `//infProt/chNFe` | ❌ **NÃO EXTRAÍDO** |

---

## 🚨 DIFERENÇAS CRÍTICAS ENCONTRADAS

### ❌ **1. Número do Título - LÓGICA DIFERENTE**

**VBA:**
```vba
' Usa nFat (número da FATURA), não nDup (número da duplicata)
nFat = XML.SelectSingleNode("//cobr/fat/nFat").Text
' Adiciona sufixo /001, /002, /004, /005, /006 baseado em MENU.B6
numero_titulo = nFat & "/001"
```

**Python (ATUAL):**
```python
# Usa nDup (número da DUPLICATA)
n_dup = _safe_find_text(dup, "nDup", ns)
numero_titulo = n_dup or numero_nota
```

**No XML de exemplo:**
- `<nFat>` (fatura) provavelmente é diferente de `<nDup>001</nDup>`
- VBA pode estar criando múltiplas parcelas a partir de uma única fatura

---

### ❌ **2. Endereço do SACADO (Destinatário) - NÃO EXTRAÍDO**

**VBA extrai:**
```vba
' Endereço do DESTINATÁRIO (sacado)
endereco = XML.SelectSingleNode("//dest/enderDest/xLgr").Text
cep = XML.SelectSingleNode("//dest/enderDest/CEP").Text
```

**Python extrai:**
```python
# Endereço do EMITENTE (cedente) - DIFERENTE!
ender_emit = _safe_find(emit, "enderEmit", ns)
```

**⚠️ PROBLEMA**: Nosso parser extrai endereço do **CEDENTE**, mas o VBA extrai endereço do **SACADO**!

---

### ❌ **3. Chave da NF-e - NÃO EXTRAÍDO**

**VBA:**
```vba
chave_nfe = XML.SelectSingleNode("//infProt/chNFe").Text
```

**Python:**
- ❌ NÃO extrai a chave da NF-e (44 dígitos)
- Esta chave é importante para rastreabilidade e validação

---

### ⚠️ **4. Sufixos de Parcelas (/001, /002, etc.)**

**VBA:**
```vba
' Adiciona sufixo baseado em número de parcelas
If MENU.B6 = 1 Then nFat & "/001"
If MENU.B6 = 2 Then nFat & "/002"
If MENU.B6 = 4 Then nFat & "/004"
' etc...
```

**Python:**
- Não tem essa lógica de parcelamento
- Cada `<dup>` no XML é tratado como título independente

---

## 📋 Campos do XML de Exemplo

Verificando no XML fornecido:

```xml
<!-- Fatura -->
<fat>
    <nFat>001</nFat>
    <vOrig>80911.50</vOrig>
    <vDesc>0.00</vDesc>
    <vLiq>80911.50</vLiq>
</fat>

<!-- Duplicata -->
<dup>
    <nDup>001</nDup>
    <dVenc>2026-07-10</dVenc>
    <vDup>80911.50</vDup>
</dup>

<!-- Endereço Destinatário -->
<enderDest>
    <xLgr>RUA JOAO BATISTA SOARES</xLgr>
    <nro>4780</nro>
    <xBairro>CENTRO</xBairro>
    <cMun>3549904</cMun>
    <xMun>SAO JOSE DOS CAMPOS</xMun>
    <UF>SP</UF>
    <CEP>12240000</CEP>
    <cPais>1058</cPais>
    <xPais>BRASIL</xPais>
    <fone>1239497000</fone>
</enderDest>

<!-- Chave NF-e -->
<infProt>
    <chNFe>35260502455462000129550010001545861524125687</chNFe>
</infProt>
```

---

## 🔧 Correções Necessárias

### **1. Adicionar extração de endereço do SACADO**
```python
# Adicionar ao parser
sacado_endereco = ""
ender_dest = _safe_find(dest, "enderDest", ns)
if ender_dest is not None:
    lgr = _safe_find_text(ender_dest, "xLgr", ns)
    nro = _safe_find_text(ender_dest, "nro", ns)
    bairro = _safe_find_text(ender_dest, "xBairro", ns)
    mun = _safe_find_text(ender_dest, "xMun", ns)
    uf = _safe_find_text(ender_dest, "UF", ns)
    cep = _safe_find_text(ender_dest, "CEP", ns)
```

### **2. Adicionar extração da chave NF-e**
```python
chave_nfe = ""
inf_prot = _safe_find(nfe, "infProt", ns)
if inf_prot is not None:
    chave_nfe = _safe_find_text(inf_prot, "chNFe", ns)
```

### **3. Adicionar extração do nFat (número da fatura)**
```python
numero_fatura = ""
fat = _safe_find(cobr, "fat", ns)
if fat is not None:
    numero_fatura = _safe_find_text(fat, "nFat", ns)
```

### **4. Adicionar campos ao Titulo model**
```python
# Novos campos necessários:
- sacado_endereco
- sacado_cep
- chave_nfe
- numero_fatura
```

---

## 🎯 Decisões de Arquitetura

### **Opção A: Adicionar TODOS os campos** ✅ RECOMENDADO
- Endereço completo do sacado
- CEP do sacado
- Chave da NF-e
- Número da fatura (nFat)
- Manter compatibilidade com sistema legado VBA

### **Opção B: Manter mínimo e adicionar depois**
- Apenas o essencial para cessão
- Adicionar campos conforme necessidade
- Risco de incompatibilidade com processos existentes

---

## 📊 Resumo Executivo

| Aspecto | VBA | Python Atual | Status |
|---------|-----|--------------|--------|
| Dados do Cedente | ✅ CNPJ + Nome | ✅ CNPJ + Nome + Endereço | ✅ OK |
| Dados do Sacado | ✅ CNPJ + Nome + Endereço + CEP | ⚠️ CNPJ + Nome (sem endereço) | ❌ FALTA |
| Número Título | `nFat` + sufixo | `nDup` | ⚠️ DIFERENTE |
| Chave NF-e | ✅ Extraído | ❌ Não extrai | ❌ FALTA |
| Parcelamento | ✅ Sufixos /001, /002... | ❌ Não implementado | ⚠️ ANALISAR |

---

## 🚀 Próximos Passos

1. **URGENTE**: Adicionar extração de endereço do sacado
2. **IMPORTANTE**: Adicionar extração da chave NF-e
3. **ANALISAR**: Lógica de parcelamento (sufixos /001, /002)
4. **VERIFICAR**: Se `nFat` vs `nDup` impacta negócio
5. **ADICIONAR**: Campos ao modelo Titulo se necessário

---

## ❓ Perguntas para o Usuário

1. **Parcelamento**: O sistema precisa criar múltiplas parcelas a partir de uma única fatura? (Como o VBA faz com sufixos /001, /002, etc.)

2. **Endereço do Sacado**: É necessário armazenar endereço completo do sacado? O VBA armazena isso.

3. **Chave NF-e**: A chave da NF-e (44 dígitos) é usada em algum processo? CNAB? Auditoria?

4. **nFat vs nDup**: Qual deve ser usado como número do título?
   - `nFat` = Número da fatura (usado pelo VBA)
   - `nDup` = Número da duplicata (usado pelo Python)

5. **Campos CNAB**: Os códigos fixos ("01", "02") no VBA são para geração de CNAB? Precisamos dessa estrutura?
