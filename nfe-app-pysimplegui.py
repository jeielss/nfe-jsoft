from io import BytesIO
from PIL import Image, ImageDraw
import requests
import lib.nfe_jsoft as nfj
import urllib3
import PySimpleGUI as sg
from datetime import datetime
import threading
import time

# Função principal

urllib3.disable_warnings()
contTime = 0
aToken = ""
selectedTab = "NFs"
thread = None
empresa = "Filial"
#Authentication
#url = "https://auth.mercadolivre.com.br/authorization?response_type=code&client_id=4929691472115145&redirect_uri=https://jeielss.github.io/nfe-mercadolivre"

attNF = False
NFs = sg.TreeData()
def fClear(): return True
tarefas = [{},{}]
sems = [threading.Semaphore(), threading.Semaphore()]
stopThread = [False,False]
endThread = [False, False]
progressThread = [0,0]
def threadFunction(id:int):

    def atualizaEstado(progresso):
        progressThread[id] = progresso
        return not stopThread[id]

    while True:
        exclusao = []
        sems[id].acquire()
        _t = tarefas[id].copy()
        sems[id].release()
        
        for n, (Func,args) in enumerate(_t.items()):
            if Func == fClear: continue
            Func(*args,atualizaEstado)
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

def main():
    global empresa, NFs, attNF
    sg.theme("LightGrey1")
    sg.set_options(font=('Helvetica', 12))
    contTime = datetime.now()
    resultadoThreading = []
    global selectedTab
    thread = threading.Thread(target=threadFunction, args=[0])
    thread.start()
    addJob(0, renovarToken, [empresa])
    
    
    check = [icon(0), icon(1), icon(2)]
    tree = sg.Tree(sg.TreeData(),["Valor", "ID"],row_height=24,metadata=[],
                   enable_events=True, key="tbNF",expand_x=True,expand_y=True,
                   right_click_menu=["", ["Copiar cliente", "Copiar ID"]],
                   select_mode=sg.SELECT_MODE_BROWSE)
    tabNF = sg.Tab("NFs",[[tree],[sg.Button("Gerar Notas"),
                                  sg.Button('Botão bonito', size=(15, 2), button_color=('white', '#475841'), font=('Helvetica', 12), border_width=0, pad=(10,10), ),
                                  sg.Combo(["Filial", "Matriz"], "Filial", key="cEmpresa", enable_events=True),
                                   sg.ProgressBar(100, key="pgBar",orientation='h', size=(20, 20))]])
    
    Orders = []
    tabFin = sg.Tab("Finanças",[[sg.Button("OK")]])

    Produtos = []
    tabEst = sg.Tab("Estoque",[[sg.Button("OK")]])
    
    tabs = [[tabNF]]#,tabEst,tabFin]]
    layout = [
            [sg.TabGroup(tabs,key="tabGroup",enable_events=True,expand_x=True,expand_y=True)]
        ]
    window = sg.Window("Manager JSoft", layout,size=(800,400),margins=(0,0),resizable=True,finalize=True)
    tree = window["tbNF"]
    tree.Widget.heading("#0", text="Cliente")
    
    
    def selectTab(tab, tAtualiza):
        if tab == "NFs":
            global NFs, attNF
            
            orders = nfj.getOrderIds(aToken, tAtualiza)
            tree.metadata = []
            NFs = sg.TreeData()
            for id, infos in orders.items():
                NFs.Insert('', id, infos[0], values=[infos[1],id,infos[2]],icon=check[1])
                tree.metadata.append(id)
            
            attNF = True
            tAtualiza(100)
            
    addJob(0, selectTab, ["NFs"])
    while True:
        diferenca = datetime.now() - contTime
        if diferenca.seconds//3600 >= 5:
            contTime = datetime.now()
            addJob(0, renovarToken, [empresa])
        event, values = window.read(100)

        pg = window["pgBar"]
        pg.UpdateBar(progressThread[0])
        if attNF:
            window.Element("tbNF").Update(values=NFs)
            attNF = False
        elif event == "tabGroup":
            tarefas[0][selectTab] = [values["tabGroup"]]
        elif event == 'cEmpresa':
            empresa = values['cEmpresa']
            resetThread(0)
            addJob(0, renovarToken, [empresa])
            addJob(0, selectTab, ["NFs"])
        elif event == 'tbNF':
            if len(values['tbNF']) > 0:
                id = values['tbNF'][0]
                if id in tree.metadata:
                    tree.metadata.remove(id)
                    tree.update(key=id, icon=check[0])
                else:
                    tree.metadata.append(id)
                    tree.update(key=id, icon=check[1])
        elif event == 'Gerar Notas':
            orders = {}
            for order in tree.metadata:
                item = NFs.tree_dict[order]
                orders[order] = item.values[2]
            addJob(0, gerarNotasGUI, [orders])
        elif event == sg.WINDOW_CLOSED:
            breakThread(0)
            breakThread(1)
            break
    window.close()

def renovarToken(emp, t):
    global aToken, empresa
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

def icon(check):
    box = (26, 22)
    background = (255, 255, 255, 0)
    rectangle = (2, 2, 20, 20)
    line = ((6, 12), (10, 16), (16, 6))
    im = Image.new('RGBA', box, background)
    draw = ImageDraw.Draw(im, 'RGBA')
    draw.rectangle(rectangle, outline='black', width=3)
    if check == 1:
        draw.line(line, fill='black', width=2, joint='curve')
    elif check == 2:
        draw.line(line, fill='grey', width=2, joint='curve')
    with BytesIO() as output:
        im.save(output, format="PNG")
        png = output.getvalue()
    return png

def gerarNotasGUI(lista, fLoop):
    global empresa, aToken
    notasFeitas = 0
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
    pacotes = {}
    for num, (idOrder, idEnvio) in enumerate(lista.items()):
        while True:
            try:
                xml = nfj.gerarNota(idOrder, aToken, numNota, empresa)
                if "Pacote" in xml:
                    id = xml.split(":")[1]
                    if id not in pacotes:
                        pacotes[id] = idEnvio
                    break
                elif not "Erro - " in xml:
                    comeco = "Sucesso: "
                    envio = nfj.enviarNotaMLB(aToken, xml, idEnvio)
                    1
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
                    break
                else:
                    print(e.mensagem)
                    break
            else: break
        fLoop(100*num/numItems)
    fLoop(100)
    
    for pacote, idEnvio in pacotes.items():
        while True:
            try:
                xml = nfj.gerarNota(pacote, aToken, numNota, empresa, True)
                if "Pacote" in xml:
                    pacotes += [xml.split(":")[1]]
                    break
                elif not "Erro - " in xml:
                    comeco = "Sucesso: "
                    envio = nfj.enviarNotaMLB(aToken, xml, idEnvio)
                    1
                else: 
                    comeco = "Falha: "
                
                print(f"{comeco} {numNota}, {pacote} - {idEnvio}")
                if comeco == "Sucesso: ":
                    notasFeitas += 1
                    numNota += 1
                else:
                    raise NFeJSOFTError(xml)

            except NFeJSOFTError as e:
                if "Rejeicao: Duplicidade de NF-e, com diferença na Chave de Acesso" in e.mensagem:
                    numNota += 1
                    break
                else:
                    print(e.mensagem)
                    break
            else: break
        fLoop(100*num/numItems)
    linhas[indArq] = linhas[indArq].replace(savedNumNota, str(numNota))
    for i, item in enumerate(linhas): 
        if not '\n' in linhas[i]: linhas[i] += "\n"
    arqDados.seek(0)
    arqDados.truncate()
    arqDados.writelines(linhas)

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

if __name__ == "__main__":
    main()

