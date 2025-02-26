import os
from io import BytesIO
import requests
import lib.nfe_jsoft as nfj
import urllib3
import flet as ft
from datetime import datetime
import threading
import time

urllib3.disable_warnings()
contTime = 0
aToken = ""
selectedTab = "NFs"
thread = None
empresa = ""
attNF = False
NFs = {}
def fClear(): return True
tarefas = [{},{}]
sems = [threading.Semaphore(), threading.Semaphore()]
stopThread = [False,False]
endThread = [False, False]
progressThread = [0,0]
loadFunction = None
def threadFunction(id:int):

    def threadProgress(progresso):
        if progresso > 0 and progresso < 100:
            loadFunction(True)
        else:
            loadFunction(False)
        progressThread[id] = progresso
        return not stopThread[id]

    while True:
        exclusao = []
        sems[id].acquire()
        _t = tarefas[id].copy()
        if len(_t.keys()) == 0:
            threadProgress(0)
        sems[id].release()
        
        for n, (Func,args) in enumerate(_t.items()):
            if Func == fClear: continue
            Func(*args,threadProgress)
            exclusao += [Func]
            sems[id].acquire()
            if stopThread[id]: 
                sems[id].release()
                break
            sems[id].release()
        sems[id].acquire()
        if fClear in tarefas[id].keys():
            tarefas[id].pop(fClear)
        else:
            for item in exclusao:
                tarefas[id].pop(item)
        
        stopThread[id] = False
        if endThread[id]:
            sems[id].release()
            break
        sems[id].release()
        time.sleep(0.2)

def addJob(idThread:int, function, args, useSem = True):
    if(useSem): sems[idThread].acquire()
    tarefas[idThread][function] = args
    if(useSem): sems[idThread].release()

def clearJobs(idThread:int, useSem = True):
    if(useSem): sems[idThread].acquire()
    tarefas[idThread].clear()
    addJob(idThread, fClear,[], False)
    if(useSem): sems[idThread].release()

def breakThread(idThread:int, useSem = True):
    if(useSem): sems[idThread].acquire()
    clearJobs(idThread, False)
    endThread[idThread] = True
    if(useSem): sems[idThread].release()

def resetThread(idThread:int, useSem = True):
    if(useSem): sems[idThread].acquire()
    stopThread[idThread] = True
    clearJobs(idThread, False)
    if(useSem): sems[idThread].release()



def main(page: ft.Page):
    global empresa,loadFunction,aToken
    
    
    def loading(state:bool):
        if state and page.splash == None:
            page.splash = ft.Row([ft.Card(ft.Container(ft.ProgressRing(),padding=5))],ft.MainAxisAlignment.CENTER)
        elif not state: page.splash = None
        page.update()
    loadFunction = loading
    def onClickItem(e):
        self = e.control
        if self.leading.name == 'circle_sharp':
            self.leading = ft.Icon(ft.icons.CIRCLE_OUTLINED)
        else:
            self.leading = ft.Icon(ft.icons.CIRCLE_SHARP)
        self.update()
    
    def selectTab(e):
        page.clean()
        for item in tabItems[int(e.data)]:
            page.add(item)
        page.update()
    
    items = []
    
    def getOrdersWNf(threadProgress):
        threadProgress(1)
        orders = nfj.getOrderIds(aToken, threadProgress)
        items.clear()
        for i,(id, infos) in enumerate(orders.items()):
            
            items.append(ft.ListTile(
                            leading=ft.Icon(ft.icons.CIRCLE_SHARP),
                            title=ft.Text(f"{infos[0]} - {id}"),
                            subtitle=ft.Text(infos[1]),
                            data=[i, id, infos],
                            on_click=onClickItem
                        ),)
        
    def selectToken(e):
        global empresa
        self = e.control
        empresa = self.value
        resetThread(0)
        addJob(0, renovarToken, [empresa])
        addJob(0, getOrdersWNf, [])
    def gerarButton(e):
        orders = {}
        for item in items:
            if item.leading.name == 'circle_sharp':
                orders[item.data[1]] = item.data[2][2]
             
        addJob(0, gerarNotasGUI, [orders])
    def baixarButton(e):
        addJob(0, renovarToken, [empresa])
        addJob(0, baixarNotas, ["202405", empresa])
    def devolverButton(e):
        addJob(0, renovarToken, [empresa])
        addJob(0, devolverNotasGUI, [[]])
        
    columnNF = ft.Column(
                    items,
                    height=500,
                    scroll=ft.ScrollMode.ALWAYS,
                    spacing=0,
                )
    optionsTokens = []
    for dados in open("data/tokens", "r"): optionsTokens += [ft.dropdown.Option(dados.split(":")[0], dados.split(":")[0])]
    tabItems = [
        [#NFs
            ft.Column([
                ft.Row([ft.Dropdown("", optionsTokens,on_change=selectToken),
                        ft.OutlinedButton(content=ft.Text(value="Gerar notas", size=20), on_click=gerarButton),
                        
                        ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Row(
                    [
                        ft.Card(
                            content=ft.Container(
                                width=500,
                                content=columnNF,
                                padding=ft.padding.symmetric(vertical=10),
                                
                            )
                        )
                    ],
                    
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                ft.Row([
                    ft.OutlinedButton(content=ft.Text(value="Baixar Notas Mes", size=20), on_click=baixarButton),
                    ft.OutlinedButton(content=ft.Text(value="Devolver Nota", size=20), on_click=devolverButton)
                ])
                
                
            ], scroll=ft.ScrollMode.AUTO, expand=True),
            
            
        ],
        [],
        []
    ]
   
    page.title = "Manager Jsoft"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationDestination(icon=ft.icons.LIST, label="Notas Fiscais"),
            ft.NavigationDestination(icon=ft.icons.MONEY, label="Finanças"),
            ft.NavigationDestination(icon=ft.icons.STORAGE, label="Estoque"),
        ],
        on_change=selectTab
    )
    
    for item in tabItems[0]:
        page.add(item)
    
    global empresa, NFs, attNF
    
    contTime = datetime.now()
    resultadoThreading = []
    global selectedTab
    thread = threading.Thread(target=threadFunction, args=[0])
    thread.start()
    addJob(0, renovarToken, [empresa])
    
    
    

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

def baixarNotas(mes, nome, threadProgress):
    global aToken
    nfj.baixarNotasMes(aToken, mes, nome, threadProgress)

def devolverNotasGUI(lista, threadProgress):
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
    numItems = len(lista)
    notasFeitas = 0
    enviosFeitos = 0
    pacotes = []
    threadProgress(1)
    for num, idOrder in enumerate(lista):
        try:
            xml = nfj.gerarNotaDevolucao(idOrder, aToken, numNota, empresa)
            if "Pacote" in xml:
                id = xml.split(":")[1]
                if id not in pacotes.keys():
                    pacotes += [id]
                    xml = nfj.gerarNotaDevolucao(id, aToken, numNota, empresa, True)
                else: continue

            if not "Erro - " in xml:
                comeco = "Sucesso: "
                diretorio = f"notasGeradas/devolucao/{datetime.now().month}-{datetime.now().year}"
                os.makedirs(diretorio, exist_ok=True)
                arq = open(f"{diretorio}/nf{numNota}.xml", "w")
                arq.write(xml)
                arq.close()
                notasFeitas += 1
                numNota += 1
                
            else: 
                comeco = "Falha na geração da nota: "
                erro = xml
            
            
            if ("Sucesso" not in comeco):
                print(f"{comeco} {numNota}, {idOrder}")
                raise NFeJSOFTError(erro)
            else:
                print(f"{comeco} {numNota - 1}, {idOrder}")

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
                    diretorio = f"notasGeradas/envio/{datetime.now().month}-{datetime.now().year}"
                    os.makedirs(diretorio, exist_ok=True)
                    arq = open(f"{diretorio}/nf{numNota}.xml", "w")
                    arq.write(xml)
                    arq.close()
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

if __name__ == "__main__":
    ft.app(main)

