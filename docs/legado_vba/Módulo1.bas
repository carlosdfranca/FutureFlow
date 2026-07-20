Attribute VB_Name = "Módulo1"
Sub arquivo()
Dim DTL As Date
Dim CDO As String
Dim OCO As String
Dim caminho As String
Dim iArq As Long

iArq = FreeFile

Application.FileDialog(msoFileDialogFolderPicker).Show
caminho = Application.FileDialog(msoFileDialogFolderPicker).SelectedItems(1)

Open caminho & "\cnab.txt" For Output As iArq

DTL = Sheets("MENU").Range("DTL").Value
CDO = Sheets("MENU").Range("CDO").Value
OCO = Sheets("MENU").Range("OCORRENCIA").Value
For i = 1 To 470000
    If Sheets("BASE").Cells(i, 3).Value = "" Then
        Exit For
    Else
        If i = 1 Then
            Print #iArq, "0" _
                    & "1" _
                    & "REMESSA" _
                    & "01" _
                    & "COBRANCA       " _
                    & REP("0", 20 - Len(CDO)) & CDO _
                    & REP("W", 30) _
                    & "001" _
                    & REP("B", 15) _
                    & Mid(DTL, 1, 2) & Mid(DTL, 4, 2) & Mid(DTL, 9, 2) _
                    & REP(" ", 8) _
                    & "MX" _
                    & REP("0", 6) & "1" _
                    & REP(" ", 321) _
                    & "000001"
        Else
            X = "1" _
                & REP(" ", 6) & REP(" ", 1 - Len(Trim(Sheets("BASE").Cells(i, 19).Value))) & Trim(Sheets("BASE").Cells(i, 19).Value) & REP(" ", 2) & REP("0", 10 - Len(Replace(Sheets("BASE").Cells(i, 20).Value, ",", "") & IIf(fd(Sheets("BASE").Cells(i, 20).Value, ",") = 0, "00", "") & IIf(Left(Right(Sheets("BASE").Cells(i, 20).Value, 2), 1) = ",", "0", ""))) & Replace(Sheets("BASE").Cells(i, 20).Value, ",", "") & IIf(fd(Sheets("BASE").Cells(i, 20).Value, ",") = 0, "00", "") & IIf(Left(Right(Sheets("BASE").Cells(i, 20).Value, 2), 1) = ",", "0", "") _
                & REP("0", 2 - Len(Right(Trim(Sheets("BASE").Cells(i, 15).Value), 2))) & Left(Trim(Sheets("BASE").Cells(i, 15).Value), 2) & REP("0", 15) _
                & REP(" ", 25 - Len(Trim(Sheets("BASE").Cells(i, 3).Value))) & Trim(Sheets("BASE").Cells(i, 3).Value) _
                & "001" _
                & REP("0", 5) _
                & REP("0", 11) _
                & "1" _
                & REP("0", 10 - Len(Replace(Sheets("BASE").Cells(i, 18).Value, ",", "") & IIf(fd(Sheets("BASE").Cells(i, 18).Value, ",") = 0, "00", "") & IIf(Left(Right(Sheets("BASE").Cells(i, 18).Value, 2), 1) = ",", "0", ""))) & Replace(Sheets("BASE").Cells(i, 18).Value, ",", "") & IIf(fd(Sheets("BASE").Cells(i, 18).Value, ",") = 0, "00", "") & IIf(Left(Right(Sheets("BASE").Cells(i, 18).Value, 2), 1) = ",", "0", "") _
                & "1" _
                & "N" _
                & Mid(DTL, 1, 2) & Mid(DTL, 4, 2) & Mid(DTL, 9, 2) _
                & REP(" ", 4) _
                & " " _
                & "1" _
                & REP(" ", 2) _
                & REP("01", 1 - Len(OCO)) & OCO _
                & REP(" ", 10 - Len(Right(Trim(Sheets("BASE").Cells(i, 4).Value), 10))) & Right(Trim(Sheets("BASE").Cells(i, 4).Value), 10) _
                & Mid(Sheets("BASE").Cells(i, 5).Value, 1, 2) & Mid(Sheets("BASE").Cells(i, 5).Value, 4, 2) & Mid(Sheets("BASE").Cells(i, 5).Value, 9, 2) _
                & REP("0", 13 - Len(Replace(Sheets("BASE").Cells(i, 6).Value, ",", "") & IIf(fd(Sheets("BASE").Cells(i, 6).Value, ",") = 0, "00", "") & IIf(Left(Right(Sheets("BASE").Cells(i, 6).Value, 2), 1) = ",", "0", ""))) & Replace(Sheets("BASE").Cells(i, 6).Value, ",", "") & IIf(fd(Sheets("BASE").Cells(i, 6).Value, ",") = 0, "00", "") & IIf(Left(Right(Sheets("BASE").Cells(i, 6).Value, 2), 1) = ",", "0", "") _
                & REP("0", 3) _
                & REP("0", 5) _
                & REP("0", 2 - Len(Right(Trim(Sheets("BASE").Cells(i, 13).Value), 2))) & Right(Trim(Sheets("BASE").Cells(i, 13).Value), 2) _
                & " " _
                & Mid(Sheets("BASE").Cells(i, 14).Value, 1, 2) & Mid(Sheets("BASE").Cells(i, 14).Value, 4, 2) & Mid(Sheets("BASE").Cells(i, 14).Value, 9, 2)
            Y = REP("0", 2) _
                & REP("0", 1) & REP("0", 2 - Len(Right(Trim(Sheets("BASE").Cells(i, 16).Value), 2))) & Left(Trim(Sheets("BASE").Cells(i, 16).Value), 2) _
                & REP("0", 12) _
                & REP("0", 6) _
                & REP("0", 13) _
                & REP("0", 13 - Len(Replace(Sheets("BASE").Cells(i, 9).Value, ",", "") & IIf(fd(Sheets("BASE").Cells(i, 9).Value, ",") = 0, "00", "") & IIf(Left(Right(Sheets("BASE").Cells(i, 9).Value, 2), 1) = ",", "0", ""))) & Replace(Sheets("BASE").Cells(i, 9).Value, ",", "") & IIf(fd(Sheets("BASE").Cells(i, 9).Value, ",") = 0, "00", "") & IIf(Left(Right(Sheets("BASE").Cells(i, 9).Value, 2), 1) = ",", "0", "") _
                & REP("0", 13) _
                & IIf(Trim(Sheets("BASE").Cells(i, 10).Value) = 1, "01", "02") _
                & REP("0", 14 - Len(IIf(Trim(Sheets("BASE").Cells(i, 10).Value) = 1, "000" & Right(Trim(Sheets("BASE").Cells(i, 7).Value), 11), Left(Trim(Sheets("BASE").Cells(i, 7).Value), 14)))) & IIf(Trim(Sheets("BASE").Cells(i, 10).Value) = 1, "000" & Right(Trim(Sheets("BASE").Cells(i, 7).Value), 11), Left(Trim(Sheets("BASE").Cells(i, 7).Value), 14)) _
                & Mid(Trim(Sheets("BASE").Cells(i, 8).Value), 1, 40) & REP(" ", 40 - Len(Mid(Trim(Sheets("BASE").Cells(i, 8).Value), 1, 40))) _
                & Mid(Trim(Sheets("BASE").Cells(i, 11).Value), 1, 40) & REP(" ", 40 - Len(Mid(Trim(Sheets("BASE").Cells(i, 11).Value), 1, 40))) _
                & REP(" ", 12) _
                & Left(Trim(Sheets("BASE").Cells(i, 12).Value), 8) & REP(" ", 8 - Len(Left(Trim(Sheets("BASE").Cells(i, 12).Value), 8))) _
                & Mid(Trim(Sheets("BASE").Cells(i, 2).Value), 1, 40) & REP(" ", 46 - Len(Mid(Trim(Sheets("BASE").Cells(i, 2).Value), 1, 40))) _
                & REP("0", 14 - Len(RP(Trim(Sheets("BASE").Cells(i, 1).Value)))) & RP(Trim(Sheets("BASE").Cells(i, 1).Value)) _
                & REP("0", 44 - Len(Right(Trim(Sheets("BASE").Cells(i, 17).Value), 44))) & Left(Trim(Sheets("BASE").Cells(i, 17).Value), 44) & REP("0", 6 - Len(i)) & i
            Print #iArq, X & Y
            X = ""
            Y = ""
            
        End If
    End If
Next
Print #iArq, "9" _
                                        & REP(" ", 437) _
                                        & REP("0", 6 - Len(i)) & i
Close #iArq


End Sub
Public Function REP(X As String, Y As Integer)
Dim Z As String
For i = 1 To Y
    Z = Z & X
Next
REP = Z
End Function

Public Function fd(X As String, Y As String)
For i = 1 To Len(X)
    If Mid(X, i, 1) = Y Then
        fd = 1
        Exit For
    Else
        fd = 0
    End If
Next
End Function
Public Function RP(X As String)
    RP = Replace(Replace(Replace(X, "/", ""), ".", ""), "-", "")
End Function



Sub a()
AB = fd("AAABAAA", "C")
End Sub
