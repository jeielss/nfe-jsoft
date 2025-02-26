from io import BytesIO
import requests
import lib.nfe_jsoft as nfj
import urllib3
import flet as ft
from datetime import datetime

urllib3.disable_warnings()
aToken = ""
selectedTab = "NFs"
empresa = ""
attNF = False
NFs = {}

def renovarToken(emp, threadProgress):
    global aToken, empresa
    threadProgress(1)
    empresa = emp
    arqDados = open("data/tokens", "r+")
    linhas = arqDados.readlines().copy()
    indArq = 0
    for i, dados in enumerate(linhas):
        if (f"{empresa}: " in dados):
            savedRToken = dados.split(f"{empresa}: ")[1].replace("\n",'')
            tokens = nfj.renovarAccessToken(savedRToken)
            indArq = i
            break
    
    aToken = tokens[0]
    rToken = tokens[1]
    linhas[indArq] = linhas[indArq].replace(savedRToken, rToken)
    arqDados.seek(0)
    arqDados.truncate()
    arqDados.writelines(linhas)
    arqDados.close()
    #threadProgress(100)

def baixarNotas(mes, threadProgress):
    global aToken
    nfj.baixarNotasMes(aToken, mes, threadProgress)

def gerarNotasGUI(lista, threadProgress):
    global empresa, aToken
    
    
    arqDados = open("data/numNota", "r+")
    linhas = arqDados.readlines().copy()
    indArq = 0
    for i, dados in enumerate(linhas):
        if (f"{empresa}: " in dados):
            savedNumNota = (dados.split(f"{empresa}: ")[1].replace("\n",''))
            indArq = i
            break
    numNota = int(savedNumNota)
    numItems = len(lista.keys())
    notasFeitas = 0
    enviosFeitos = 0
    pacotes = {}
    threadProgress(1)
    for num, (idOrder, idEnvio) in enumerate(lista.items()):
        try:
            xml = nfj.gerarNota(idOrder, aToken, numNota, empresa)
            if "Pacote" in xml:
                id = xml.split(":")[1]
                if id not in pacotes.keys():
                    pacotes[id] = idEnvio
                    xml = nfj.gerarNota(id, aToken, numNota, empresa, True)
                else: continue

            if not "Erro - " in xml:
                envio = nfj.enviarNotaMLB(aToken, xml, idEnvio)
                if envio.status_code == 201:
                    enviosFeitos += 1
                    comeco = "Sucesso: "
                else:
                    comeco = "Falha no envio ao ML: "
                    log = open(f"log/nf{numNota}.xml", "w")
                    log.write(xml)
                    log.close()
                    erro = envio.content
                notasFeitas += 1
                numNota += 1
            else: 
                comeco = "Falha na geração da nota: "
                erro = xml
            
            print(f"{comeco} {numNota - 1}, {idOrder} - {idEnvio}")
            if ("Sucesso" not in comeco):
                raise NFeJSOFTError(erro)

        except NFeJSOFTError as e:
            if "Rejeicao: Duplicidade de NF-e, com diferença na Chave de Acesso" in e.mensagem:
                numNota += 1
            else:
                print(e.mensagem)
        threadProgress(100*num/numItems)
    #threadProgress(100)
    linhas[indArq] = linhas[indArq].replace(savedNumNota, str(numNota))
    for i, item in enumerate(linhas): 
        if not '\n' in linhas[i]: linhas[i] += "\n"
    arqDados.seek(0)
    arqDados.truncate()
    arqDados.writelines(linhas)
    arqDados.close()

class NFeJSOFTError(Exception):
    def __init__(self, mensagem):
        super().__init__(mensagem)
        self.mensagem = mensagem

def gerarNotas(matriz = True):
    arqDados = open("numNota.txt", "r+")
    linhas = arqDados.readlines().copy()
    indArq = 0
    print("Autenticando...")
    for i, dados in enumerate(linhas):
        if matriz and ("Matriz: " in dados):
            savedRToken, savedNumNota = dados.split("Matriz: ")[1].split(",")
            aToken,rToken = nfj.renovarAccessToken(savedRToken)
            indArq = i
        elif not matriz and ("Filial: " in dados):
            savedRToken, savedNumNota = dados.split("Filial: ")[1].split(",")
            aToken,rToken = nfj.renovarAccessToken(savedRToken)
            indArq = i
    
    linhas[indArq] = linhas[indArq].replace(savedRToken, rToken)
    arqDados.seek(0)
    arqDados.truncate()
    arqDados.writelines(linhas)
    arqDados.flush()
    numNota = int(savedNumNota.strip())
    print("Procurando Vendas")
    ids = nfj.getOrderIds(aToken)
    print(f"{len(ids)} vendas encontradas!")
    notasFeitas = 0
    print("Processando Notas")
    for idOrder, idEnvio in ids.items():
        while True:
            try:
                xml = nfj.gerarNota(idOrder, aToken, numNota, matriz)
                if not "Erro - " in xml:
                    comeco = "Sucesso: "
                    nfj.enviarNotaMLB(aToken, xml, idEnvio)
                else: 
                    comeco = "Falha: "
                
                print(f"{comeco} {numNota}, {idOrder} - {idEnvio}")
                if comeco == "Sucesso: ":
                    notasFeitas += 1
                    numNota += 1
                else:
                    raise NFeJSOFTError(xml)

            except NFeJSOFTError as e:
                if "Rejeicao: Duplicidade de NF-e, com diferença na Chave de Acesso" in e.mensagem:
                    numNota += 1
                    print("Tentando novamente")
                    continue  # Continue para a próxima iteração do loop while
                else:
                    print(e.mensagem)
                    break
            else: break
        

    linhas[indArq] = linhas[indArq].replace(savedNumNota, str(numNota))
    for i, item in enumerate(linhas): 
        if not '\n' in linhas[i]: linhas[i] += "\n"
    arqDados.seek(0)
    arqDados.truncate()
    arqDados.writelines(linhas)
    arqDados.close()
    
    empresa = "Matriz"
    if not matriz: empresa = "Filial"

    if notasFeitas <= 0:
        print(f"Nenhuma nota foi feita com sucesso para {empresa}!")
    elif notasFeitas == 1:
        print(f"1 nota foi feita com sucesso para {empresa}!")
    else:
        print(f"{notasFeitas} notas foram feitas com sucesso para {empresa}!")

def gerarNota(idOrder, idEnvio, atoken, numNota, matriz):
    xml = nfj.gerarNota(idOrder, atoken, numNota, matriz)
    if xml != "":
        teste = nfj.enviarNotaMLB(atoken, xml, idEnvio)
        print("Enviada", numNota)
    else: print("Erro")

