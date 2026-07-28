Attribute VB_Name = "Módulo3"
' ============================================================
' FUNÇÃO PARA CALCULAR DESCONTO COM ARREDONDAMENTO
' ============================================================
Function CalcularDesconto(valorOriginal As Variant) As Variant
    Dim valor As Double
    
    On Error Resume Next
    
    If IsEmpty(valorOriginal) Then
        CalcularDesconto = ""
        Exit Function
    End If
    
    valorOriginal = Trim(CStr(valorOriginal))
    
    If valorOriginal = "" Or valorOriginal = "0" Then
        CalcularDesconto = ""
        Exit Function
    End If
    
    valor = CDbl(valorOriginal)
    CalcularDesconto = Round(valor * 0.994, 2)
    
    On Error GoTo 0
End Function

' ============================================================
' FUNÇÃO PARA FORMATAR VALOR COM 2 CASAS DECIMAIS
' ============================================================
Function FormatarValorDecimal(valor As Variant) As String
    Dim valorNum As Double
    Dim parteInteira As Long
    Dim parteDecimal As Long
    Dim strDecimal As String
    
    On Error Resume Next
    
    If IsEmpty(valor) Or valor = "" Then
        FormatarValorDecimal = ""
        Exit Function
    End If
    
    valorNum = CDbl(valor)
    valorNum = Round(valorNum, 2)
    
    parteInteira = Fix(valorNum)
    parteDecimal = Round((valorNum - parteInteira) * 100, 0)
    
    strDecimal = Format(parteDecimal, "00")
    
    FormatarValorDecimal = CStr(parteInteira) & "," & strDecimal
    
    On Error GoTo 0
End Function

' ============================================================
' FUNÇÃO PARA REMOVER CARACTERES ESPECIAIS E PONTOS
' ============================================================
Function RemoverCaracteresEspeciais(texto As String) As String
    Dim resultado As String
    Dim i As Integer
    Dim caractere As String
    Dim codigo As Integer
    Dim textoSemPontos As String
    
    On Error Resume Next
    
    If texto = "" Then
        RemoverCaracteresEspeciais = ""
        Exit Function
    End If
    
    textoSemPontos = Replace(texto, ".", "")
    
    resultado = ""
    
    For i = 1 To Len(textoSemPontos)
        caractere = Mid(textoSemPontos, i, 1)
        codigo = Asc(caractere)
        
        Select Case codigo
            Case 192 To 197: caractere = "A"
            Case 224 To 229: caractere = "a"
            Case 200 To 203: caractere = "E"
            Case 232 To 235: caractere = "e"
            Case 204 To 207: caractere = "I"
            Case 236 To 239: caractere = "i"
            Case 210 To 214: caractere = "O"
            Case 242 To 246: caractere = "o"
            Case 217 To 220: caractere = "U"
            Case 249 To 252: caractere = "u"
            Case 199: caractere = "C"
            Case 231: caractere = "c"
            Case 195: caractere = "A"
            Case 227: caractere = "a"
            Case 209: caractere = "N"
            Case 241: caractere = "n"
        End Select
        
        If (codigo >= 48 And codigo <= 57) Or _
           (codigo >= 65 And codigo <= 90) Or _
           (codigo >= 97 And codigo <= 122) Or _
           codigo = 32 Or codigo = 44 Or codigo = 46 Then
            
            resultado = resultado & caractere
        End If
    Next i
    
    RemoverCaracteresEspeciais = resultado
    
    On Error GoTo 0
End Function

' ============================================================
' MAIN - PROCEDIMENTO PRINCIPAL
' ============================================================
Public Sub JPl()
    Dim xmlDoc As Object
    Dim arquivo As Variant
    Dim arquivos As Collection
    Dim pasta As String
    Dim arquivoXML As String
    Dim NextRow As Long
    Dim wsBase As Worksheet
    Dim wsMenu As Worksheet
    Dim wsCODIGO As Worksheet
    Dim strDataEmissao As String
    Dim strNF As String
    Dim strChaveNFe As String
    Dim i As Long

    Dim strTituloCredito As String
    Dim strCNPJDevedor As String
    Dim strValorPresente_XML As String
    Dim strValorNominal_XML As String
    Dim strVencimento_XML As String
    Dim strVencimento_Formatado As String
    Dim NextRowMENU As Long
    Dim strDataFormatadaEmissao As String

    Dim contadorProcessados As Long
    Dim contadorErros As Long

    On Error GoTo Erro_Handle

    Set wsBase = ThisWorkbook.Sheets("BASE")
    Set wsMenu = ThisWorkbook.Sheets("MENU")
    Set wsCODIGO = ThisWorkbook.Sheets("CODIGO")

    pasta = SelecionarPasta()
    If pasta = "" Then
        MsgBox "Nenhuma pasta selecionada.", vbExclamation
        Exit Sub
    End If

    Set arquivos = New Collection
    arquivoXML = Dir(pasta & "\*.xml")
    Do While arquivoXML <> ""
        arquivos.Add pasta & "\" & arquivoXML
        arquivoXML = Dir()
    Loop

    If arquivos.Count = 0 Then
        MsgBox "Nenhum arquivo XML encontrado na pasta.", vbExclamation
        Exit Sub
    End If

    contadorProcessados = 0
    contadorErros = 0

    For i = 1 To arquivos.Count
        arquivo = arquivos(i)
        
        Set xmlDoc = CreateObject("Msxml2.DOMDocument.6.0")
        xmlDoc.async = False
        xmlDoc.Load arquivo
        
        If xmlDoc.parseError.errorCode <> 0 Then
            MsgBox "Erro no XML: " & xmlDoc.parseError.reason & vbCrLf & "Arquivo: " & arquivo, vbCritical
            contadorErros = contadorErros + 1
            Set xmlDoc = Nothing
            GoTo ProximoArquivo
        End If

        xmlDoc.SetProperty "SelectionNamespaces", "xmlns:nfe='http://www.portalfiscal.inf.br/nfe'"

        NextRow = wsBase.Cells(wsBase.Rows.Count, 1).End(xlUp).Row + 1
        
        strChaveNFe = LimparPrefixoNFe(GetNodeValue(xmlDoc, "//nfe:infNFe/@Id"))
        strTituloCredito = strChaveNFe

        strValorPresente_XML = GetNodeValue(xmlDoc, "//nfe:cobr/nfe:dup/nfe:vDup")
        strValorNominal_XML = GetNodeValue(xmlDoc, "//nfe:total/nfe:ICMSTot/nfe:vNF")

        strVencimento_XML = GetNodeValue(xmlDoc, "//nfe:cobr/nfe:dup/nfe:dVenc")
        strVencimento_Formatado = ExtrairData(strVencimento_XML)

        strDataEmissao = GetNodeValue(xmlDoc, "//nfe:ide/nfe:dhEmi")
        strDataFormatadaEmissao = ExtrairData(strDataEmissao)

        strNF = GetNodeValue(xmlDoc, "//nfe:cobr/nfe:fat/nfe:nFat")

        Dim strNomeEmitente As String
        Dim strNomeDevedor As String
        Dim strValorFormatado As String
        Dim strCEP As String
        
        strNomeEmitente = RemoverPontos(GetNodeValue(xmlDoc, "//nfe:emit/nfe:xNome"))
        strNomeDevedor = RemoverCaracteresEspeciais(GetNodeValue(xmlDoc, "//nfe:dest/nfe:xNome"))
        strCEP = GetNodeValue(xmlDoc, "//nfe:dest/nfe:enderDest/nfe:CEP")
        
        strValorFormatado = FormatarValor(strValorPresente_XML)

        With wsBase
            .Cells(NextRow, 1).Value = GetNodeValue(xmlDoc, "//nfe:emit/nfe:CNPJ")
            .Cells(NextRow, 2).Value = strNomeEmitente
            .Cells(NextRow, 3).Value = strNF
            .Cells(NextRow, 4).Value = strNF
            .Cells(NextRow, 5).NumberFormat = "@"
            .Cells(NextRow, 5).Value = strVencimento_Formatado
            .Cells(NextRow, 6).NumberFormat = "@"
            .Cells(NextRow, 6).Value = strValorFormatado
            .Cells(NextRow, 7).Value = GetNodeValue(xmlDoc, "//nfe:dest/nfe:CNPJ")
            .Cells(NextRow, 8).Value = strNomeDevedor
            .Cells(NextRow, 10).Value = "02"
            .Cells(NextRow, 11).Value = ""
            .Cells(NextRow, 12).Value = strCEP
            .Cells(NextRow, 13).Value = 1
            .Cells(NextRow, 14).NumberFormat = "@"
            .Cells(NextRow, 14).Value = strDataFormatadaEmissao
            .Cells(NextRow, 15).Value = 2
            .Cells(NextRow, 16).Value = "02"
            .Cells(NextRow, 17).Value = GetNodeValue(xmlDoc, "//nfe:infProt/nfe:chNFe")
        End With

        strCNPJDevedor = GetNodeValue(xmlDoc, "//nfe:dest/nfe:CNPJ")
        
        NextRowMENU = wsMenu.Cells(wsMenu.Rows.Count, 9).End(xlUp).Row + 1
        If NextRowMENU < 2 Then NextRowMENU = 2

        With wsMenu
            .Cells(NextRowMENU, 8).Value = "Duplicata"
            .Cells(NextRowMENU, 9).Value = strCNPJDevedor
            .Cells(NextRowMENU, 10).NumberFormat = "@"
            .Cells(NextRowMENU, 10).Value = strValorFormatado
            .Cells(NextRowMENU, 11).NumberFormat = "@"
            .Cells(NextRowMENU, 11).Value = strVencimento_Formatado
            .Cells(NextRowMENU, 12).Value = strNF
        End With

        contadorProcessados = contadorProcessados + 1

ProximoArquivo:
        Set xmlDoc = Nothing
    Next i

    Dim NextRowMENU_Fim As Long
    Dim strValorOriginal As String
    Dim valorComDesconto As Variant
    Dim valorFormatado As String
    
    NextRowMENU_Fim = wsMenu.Cells(wsMenu.Rows.Count, 10).End(xlUp).Row
    
    For i = 3 To NextRowMENU_Fim
        strValorOriginal = wsMenu.Cells(i, 10).Value
        
        If strValorOriginal <> "" Then
            valorComDesconto = CalcularDesconto(strValorOriginal)
            valorFormatado = FormatarValorDecimal(valorComDesconto)
            
            wsMenu.Cells(i, 10).NumberFormat = "@"
            wsMenu.Cells(i, 10).Value = valorFormatado
        End If
    Next i
    
    Dim NextRowBASE As Long
    Dim valorComDesconto_2 As Variant
    
    NextRowMENU_Fim = wsMenu.Cells(wsMenu.Rows.Count, 10).End(xlUp).Row
    NextRowBASE = 2
    
    For i = 3 To NextRowMENU_Fim
        valorComDesconto_2 = wsMenu.Cells(i, 10).Value
        
        If valorComDesconto_2 <> "" Then
            wsBase.Cells(NextRowBASE, 6).NumberFormat = "@"
            wsBase.Cells(NextRowBASE, 6).Value = valorComDesconto_2
            
            NextRowBASE = NextRowBASE + 1
        End If
    Next i

    MsgBox "Importação concluída!" & vbCrLf & _
           "Arquivos processados: " & contadorProcessados & vbCrLf & _
           "Arquivos com erro: " & contadorErros, vbInformation

    Exit Sub

Erro_Handle:
    MsgBox "Erro: " & Err.Description, vbCritical
End Sub

' ========================= FUNÇÕES AUXILIARES ===========================

Private Function SelecionarPasta() As String
    Dim fd As FileDialog
    Dim caminho As String
    
    On Error Resume Next
    
    Set fd = Application.FileDialog(msoFileDialogFolderPicker)
    
    With fd
        .Title = "Selecione a pasta com os arquivos XML"
        .AllowMultiSelect = False
        
        If .Show = -1 Then
            caminho = .SelectedItems(1)
            SelecionarPasta = caminho
        Else
            SelecionarPasta = ""
        End If
    End With
    
    Set fd = Nothing
    On Error GoTo 0
End Function

Function GetNodeValue(xmlDoc As Object, xPath As String) As String
    Dim node As Object
    On Error Resume Next
    Set node = xmlDoc.SelectSingleNode(xPath)
    If node Is Nothing Then
        GetNodeValue = ""
    Else
        GetNodeValue = Trim(node.Text)
    End If
    On Error GoTo 0
End Function

Function ExtrairData(dataXML As String) As String
    Dim dia As String
    Dim mes As String
    Dim ano As String
    On Error Resume Next
    
    If Len(Trim(dataXML)) = 0 Then
        ExtrairData = ""
        Exit Function
    End If
    
    If Len(dataXML) < 8 Then
        ExtrairData = dataXML
        Exit Function
    End If
    
    ano = Left(dataXML, 4)
    mes = Mid(dataXML, 6, 2)
    dia = Mid(dataXML, 9, 2)
    
    If IsNumeric(ano) And IsNumeric(mes) And IsNumeric(dia) Then
        ExtrairData = dia & "/" & mes & "/" & ano
    Else
        ExtrairData = dataXML
    End If
    
    On Error GoTo 0
End Function

Function LimparPrefixoNFe(chave As String) As String
    Dim resultado As String
    resultado = Trim(chave)
    If Len(resultado) >= 3 Then
        If LCase(Left(resultado, 3)) = "nfe" Then
            resultado = Mid(resultado, 4)
        End If
    End If
    LimparPrefixoNFe = resultado
    On Error GoTo 0
End Function

Function RemoverPontos(texto As String) As String
    On Error Resume Next
    If texto = "" Then
        RemoverPontos = ""
        Exit Function
    End If
    RemoverPontos = Replace(texto, ".", "")
    On Error GoTo 0
End Function

Function FormatarValor(valorXML As String) As String
    Dim parteInteira As String
    Dim parteDecimal As String
    Dim valorLimpo As String
    Dim posicaoPonto As Integer
    
    On Error Resume Next
    
    If valorXML = "" Or valorXML = "0" Then
        FormatarValor = ""
        Exit Function
    End If
    
    posicaoPonto = InStr(valorXML, ".")
    
    If posicaoPonto > 0 Then
        parteInteira = Left(valorXML, posicaoPonto - 1)
        parteDecimal = Mid(valorXML, posicaoPonto + 1)
        
        Do While Len(parteDecimal) < 2
            parteDecimal = parteDecimal & "0"
        Loop
        
        parteDecimal = Left(parteDecimal, 2)
        FormatarValor = parteInteira & "," & parteDecimal
    Else
        valorLimpo = valorXML
        
        Do While Len(valorLimpo) < 2
            valorLimpo = "0" & valorLimpo
        Loop
        
        parteInteira = Left(valorLimpo, Len(valorLimpo) - 2)
        parteDecimal = Right(valorLimpo, 2)
        
        If parteInteira = "" Then parteInteira = "0"
        
        FormatarValor = parteInteira & "," & parteDecimal
    End If
    
    On Error GoTo 0
End Function

