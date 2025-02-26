from decimal import Decimal
import time
import requests
from pynfe.processamento.comunicacao import ComunicacaoSefaz
from pynfe.entidades.cliente import Cliente
from pynfe.entidades.emitente import Emitente
from pynfe.entidades.notafiscal import NotaFiscal, NotaFiscalReferenciada
from pynfe.entidades.fonte_dados import _fonte_dados
from pynfe.processamento.serializacao import SerializacaoXML
from pynfe.processamento.assinatura import AssinaturaA1
from pynfe.utils.flags import CODIGO_BRASIL
from decimal import Decimal
from datetime import datetime
from lib.lists import UF
import settings
import xml.etree.ElementTree as ET
import pandas as pd

import zipfile
import io

semTaxa = True
tabelaCodMun = pd.read_csv("data/codigoMunicipio.csv", sep = ",")
def buscaCep(cep):
    cep = str(cep)
    json = requests.get(f'https://viacep.com.br/ws/{cep}/json/').json()
    if "erro" in json.keys():
        json = requests.get(f'https://viacep.com.br/ws/{cep[:-1]+"1"}/json/').json()
    codigo = int(json["ibge"])
    searchR = tabelaCodMun[tabelaCodMun["Codigo"] == codigo]
    mun = searchR.to_numpy()[0][1]
    uf = json["uf"]
    return mun, uf, str(codigo)

def codigoTitulo(Titulo):
    palavras = Titulo.split()
    primeiras_letras = ""
    for palavra in palavras:
        primeiras_letras += palavra[0]
    return primeiras_letras
def ncmTitulo(Titulo: str):
    with open('data/ncmPalavrachave', 'r') as arq:
        for linha in arq.readlines():
            ncm, palavrasChave = linha.split(" ")
            palavrasChave = palavrasChave.strip().split(",")
            for pC in palavrasChave:
                if pC.upper() in Titulo.upper(): return ncm
    return ""

def totalTributos(produtos, frete, tipo_documento):
    tributos = 0
    qtdProdutos = 0
    for produto in produtos:
        qtdProdutos += produto["quantity"]
    for produto in produtos:
        if tipo_documento == "CPF":
            if semTaxa:
                valor = produto["quantity"]*(produto["unit_price"] - frete/qtdProdutos)
            else:
                valor = produto["quantity"]*(produto["unit_price"]  - produto["sale_fee"] - frete/qtdProdutos)
        else:
            valor = produto["quantity"]*(produto["unit_price"])
        tributos += round(valor*0.04, 2)
    return tributos

def obterNota(idOrder, atoken):
    header = {
        'Authorization' : f'Bearer {atoken}',
    }
    SellerId = obterIdVendedor(atoken)

    
    return requests.get(f"http://api.mercadolibre.com/users/{SellerId}/invoices/orders/{idOrder}", headers= header)


def gerarNotaDevolucao(idOrder, atoken, numNota, nomeEmpresa, pacote=False, homologacao=False):
    if nomeEmpresa not in settings.empresas.keys(): return "Erro - Empresa não encontrada"
    
    auth_header = {'Authorization': f'Bearer {atoken}'}
    
    certificado = settings.empresas[nomeEmpresa]["certificado"]
    senha = settings.empresas[nomeEmpresa]["senha"]
    emitente = settings.empresas[nomeEmpresa]["emitente"]
    _municipioIBGE = settings.empresas[nomeEmpresa]["municipioIBGE"]
    uf = emitente.endereco_uf

    #Pacote
    if pacote:
        r = requests.get(f"https://api.mercadolibre.com/packs/{idOrder}", headers=auth_header)
        produtos = []
        _json = r.json()
        for order in _json["orders"]:
            id = order['id']
            rTmp = requests.get(f"https://api.mercadolibre.com/orders/{id}", headers=auth_header)
            _jsonTmp = rTmp.json()
            produtos += _jsonTmp["order_items"].copy()
            idOrder = id
        idEnvio = _json["shipment"]["id"]
        frete = getShipCost(atoken, idEnvio)
    
    else:
        #Detalhes do Pedido
        r = requests.get(f"https://api.mercadolibre.com/orders/{idOrder}", headers=auth_header)
        _json = r.json()
        try:
            erro = _json["error"]
            return f"Erro - {erro}"
        except:1
        produtos = _json["order_items"].copy()
        idEnvio = _json["shipping"]["id"]
        frete = getShipCost(atoken, idEnvio)
        if _json["pack_id"] != None:
            packID = str(_json["pack_id"])
            return "Pacote:" + packID

    #Destinatario
    r = requests.get(f"https://api.mercadolibre.com/orders/{idOrder}/billing_info", headers=auth_header)
    _json = r.json()
    infoDest = _json["billing_info"]

    def selectInfo(tipo):
        for info in infoDest['additional_info']:
            if info["type"] == tipo: return info["value"]
        return ""
    _tipo_documento = infoDest['doc_type']
    _numero_documento = infoDest['doc_number']
    _inscricao_estadual = str()
    _indicador_ie = 9
    if _tipo_documento == "CPF":
        _razao_social = (selectInfo("FIRST_NAME") + " " + selectInfo("LAST_NAME")).strip()
    else:
        _razao_social = selectInfo("BUSINESS_NAME")
        _inscricao_estadual = selectInfo('STATE_REGISTRATION')
        if(_inscricao_estadual != ""):
            _indicador_ie = 1

    _endereco_logradouro = selectInfo("STREET_NAME").strip()
    if len(_endereco_logradouro) < 3: _endereco_logradouro = "Rua " + _endereco_logradouro

    _endereco_numero = selectInfo("STREET_NUMBER").strip()
    _endereco_cep = selectInfo("ZIP_CODE").strip()

    _endereco_bairro = selectInfo("NEIGHBORHOOD").strip()
    _endereco_uf = UF[selectInfo("STATE_NAME").strip()]
    if _endereco_bairro == "": _endereco_bairro = "Centro"
    try:
        _endereco_municipio, _endereco_uf, codMun = buscaCep(_endereco_cep)
    except:
        _endereco_municipio, codMun = selectInfo("CITY_NAME").strip(), ""
    
    
    
    

    cliente = Cliente(
        razao_social=_razao_social,
        tipo_documento=_tipo_documento,           #CPF ou CNPJ
        #email='email@email.com',
        numero_documento=_numero_documento, # numero do cpf ou cnpj
        indicador_ie=_indicador_ie,                 # 9=Não contribuinte 
        inscricao_estadual = _inscricao_estadual,
        endereco_logradouro=_endereco_logradouro,
        endereco_numero=_endereco_numero,
        #endereco_complemento='Ao lado de lugar nenhum',
        endereco_bairro=_endereco_bairro,
        endereco_municipio=_endereco_municipio,
        endereco_cod_municipio=codMun,
        endereco_uf=_endereco_uf,
        endereco_cep=_endereco_cep,
        endereco_pais=CODIGO_BRASIL,
        #endereco_telefone='11912341234',
    )

    
    nota_fiscal = NotaFiscal(
        emitente=emitente,
        cliente=cliente,
        uf=emitente.endereco_uf,
        natureza_operacao='Devolução', # venda, compra, transferência, devolução, etc
        forma_pagamento=0,         # 0=Pagamento à vista; 1=Pagamento a prazo; 2=Outros.
        tipo_pagamento=90,
        modelo=55,                 # 55=NF-e; 65=NFC-e
                    # Número do Documento Fiscal.
        data_emissao=datetime.now(),
        data_saida_entrada=datetime.now(),
        tipo_documento=0,          # 0=entrada; 1=saida
        municipio=_municipioIBGE,       # Código IBGE do Município 
        tipo_impressao_danfe=1,    # 0=Sem geração de DANFE;1=DANFE normal, Retrato;2=DANFE normal Paisagem;3=DANFE Simplificado;4=DANFE NFC-e;
        forma_emissao=1,         # 1=Emissão normal (não em contingência);
                    # 0=Normal;1=Consumidor final;
        indicador_intermediador=0,
        finalidade_emissao='4',    # 1=NF-e normal;2=NF-e complementar;3=NF-e de ajuste;4=Devolução de mercadoria.
        processo_emissao='0',      #0=Emissão de NF-e com aplicativo do contribuinte;
        transporte_modalidade_frete=1,
        informacoes_adicionais_interesse_fisco='',
        totais_tributos_aproximado=Decimal(totalTributos(produtos,frete,_tipo_documento)),
        indicador_presencial=2,


        serie='1',
        numero_nf=str(numNota), 
        indicador_destino=(lambda x: 1 if x == emitente.endereco_uf else 2)(_endereco_uf),
        cliente_final=1,
    )
    
    nota_fiscal.adicionar_responsavel_tecnico(**settings.responsavelTecnico)

    chave_de_acesso = obterNota(idOrder, atoken).json()["attributes"]["invoice_key"]
    nota_fiscal.adicionar_nota_fiscal_referenciada(
        chave_acesso =chave_de_acesso,
    )
    
    def adicionaProdutos(produtos):
        qtdProdutos = 0
        for produto in produtos:
            qtdProdutos += produto["quantity"]
        for produto in produtos:
            _descricao = produto["item"]["title"]
            _codigo = codigoTitulo(_descricao)
            _ncm = ncmTitulo(_descricao)
            if _ncm == "": 
                return False
            _quantidade_comercial=Decimal(produto["quantity"])
            if _endereco_uf != emitente.endereco_uf: _cfop = '2202'
            else: _cfop = "1202" 
            if _tipo_documento == "CPF":
                if semTaxa:
                    _valor_unitario_comercial = (produto["unit_price"] - frete/qtdProdutos)
                else:
                    _valor_unitario_comercial = (produto["unit_price"]  - produto["sale_fee"] - frete/qtdProdutos)
                #_valor_unitario_comercial= Decimal(round(produto["unit_price"] - frete/qtdProdutos, 2))
            else:
                _valor_unitario_comercial= Decimal(round(produto["unit_price"],2))
            _valor_total_bruto=Decimal(round(_valor_unitario_comercial*_quantidade_comercial, 2))
            _quantidade_tributavel=_quantidade_comercial
            _valor_unitario_tributavel=_valor_unitario_comercial
            _valor_tributos_aprox=str(round(Decimal(0.04)*_valor_unitario_tributavel*_quantidade_tributavel,2))
            nota_fiscal.adicionar_produto_servico(
                codigo=_codigo,                           # id do produto
                descricao=_descricao,
                ncm=_ncm,
                #cest='0100100',                            # NT2015/003
                cfop=_cfop,
                unidade_comercial='UN',
                ean='SEM GTIN',
                ean_tributavel='SEM GTIN',
                quantidade_comercial=_quantidade_comercial,        # 12 unidades
                valor_unitario_comercial=_valor_unitario_comercial,  # preço unitário
                valor_total_bruto=_valor_total_bruto,       # preço total
                unidade_tributavel='UN',
                quantidade_tributavel=_quantidade_tributavel,
                valor_unitario_tributavel=_valor_unitario_tributavel,
                ind_total=1,
                # numero_pedido='12345',                   # xPed
                # numero_item='123456',                    # nItemPed
                icms_modalidade='102',
                icms_origem=0,
                icms_csosn='400',
                pis_modalidade='07',
                cofins_modalidade='07',
                valor_tributos_aprox=_valor_tributos_aprox
            )
        return True
    if adicionaProdutos(produtos) == False:
        return "Erro - Não há um ncm associado ao tipo de produto"
    serializador = SerializacaoXML(_fonte_dados, homologacao=homologacao)
    nfe = serializador.exportar()

    # assinatura
    a1 = AssinaturaA1(certificado, senha)
    xml = a1.assinar(nfe)
    # envio
    con = ComunicacaoSefaz(uf, certificado, senha, homologacao)
    time.sleep(0.01)
    envio = con.autorizacao(modelo='nfe', nota_fiscal=xml,contingencia=False)
    # em caso de sucesso o retorno será o xml autorizado
    # Ps: no modo sincrono, o retorno será o xml completo (<nfeProc> = <NFe> + <protNFe>)
    # no modo async é preciso montar o nfeProc, juntando o retorno com a NFe  
    from lxml import etree
    if envio[0] == 0:
        return (etree.tostring(envio[1], encoding="unicode").replace('\n','').replace('ns0:','').replace(':ns0', ''))
    else:
        _xml = envio[1].text
        erro = _xml.split("xMotivo>")
        contagem = _xml.count("xMotivo")
        return "Erro - " + erro[_xml.count("xMotivo") -1][:-2]

def gerarNota(idOrder, atoken, numNota, nomeEmpresa, pacote=False, homologacao=False):
    
    if nomeEmpresa not in settings.empresas.keys(): return "Erro - Empresa não encontrada"
    
    auth_header = {'Authorization': f'Bearer {atoken}'}
    
    certificado = settings.empresas[nomeEmpresa]["certificado"]
    senha = settings.empresas[nomeEmpresa]["senha"]
    emitente = settings.empresas[nomeEmpresa]["emitente"]
    _municipioIBGE = settings.empresas[nomeEmpresa]["municipioIBGE"]
    uf = emitente.endereco_uf

    #Pacote
    if pacote:
        r = requests.get(f"https://api.mercadolibre.com/packs/{idOrder}", headers=auth_header)
        produtos = []
        _json = r.json()
        for order in _json["orders"]:
            id = order['id']
            rTmp = requests.get(f"https://api.mercadolibre.com/orders/{id}", headers=auth_header)
            _jsonTmp = rTmp.json()
            produtos += _jsonTmp["order_items"].copy()
            idOrder = id
        idEnvio = _json["shipment"]["id"]
        frete = getShipCost(atoken, idEnvio)
    
    else:
        #Detalhes do Pedido
        r = requests.get(f"https://api.mercadolibre.com/orders/{idOrder}", headers=auth_header)
        _json = r.json()
        produtos = _json["order_items"].copy()
        idEnvio = _json["shipping"]["id"]
        frete = getShipCost(atoken, idEnvio)
        if _json["pack_id"] != None:
            packID = str(_json["pack_id"])
            return "Pacote:" + packID

    #Destinatario
    r = requests.get(f"https://api.mercadolibre.com/orders/{idOrder}/billing_info", headers=auth_header)
    _json = r.json()
    infoDest = _json["billing_info"]

    def selectInfo(tipo):
        for info in infoDest['additional_info']:
            if info["type"] == tipo: return info["value"]
        return ""
    _tipo_documento = infoDest['doc_type']
    _numero_documento = infoDest['doc_number']
    _inscricao_estadual = str()
    _indicador_ie = 9
    if _tipo_documento == "CPF":
        _razao_social = (selectInfo("FIRST_NAME") + " " + selectInfo("LAST_NAME")).strip()
    else:
        _razao_social = selectInfo("BUSINESS_NAME")
        _inscricao_estadual = selectInfo('STATE_REGISTRATION')
        if(_inscricao_estadual != ""):
            _indicador_ie = 1

    _endereco_logradouro = selectInfo("STREET_NAME").strip()
    if len(_endereco_logradouro) < 3: _endereco_logradouro = "Rua " + _endereco_logradouro

    _endereco_numero = selectInfo("STREET_NUMBER").strip()
    _endereco_cep = selectInfo("ZIP_CODE").strip()

    _endereco_bairro = selectInfo("NEIGHBORHOOD").strip()
    _endereco_uf = UF[selectInfo("STATE_NAME").strip()]
    if _endereco_bairro == "": _endereco_bairro = "Centro"
    try:
        _endereco_municipio, _endereco_uf, codMun = buscaCep(_endereco_cep)
    except:
        _endereco_municipio, codMun = selectInfo("CITY_NAME").strip(), ""
    
    
    
    

    cliente = Cliente(
        razao_social=_razao_social,
        tipo_documento=_tipo_documento,           #CPF ou CNPJ
        #email='email@email.com',
        numero_documento=_numero_documento, # numero do cpf ou cnpj
        indicador_ie=_indicador_ie,                 # 9=Não contribuinte 
        inscricao_estadual = _inscricao_estadual,
        endereco_logradouro=_endereco_logradouro,
        endereco_numero=_endereco_numero,
        #endereco_complemento='Ao lado de lugar nenhum',
        endereco_bairro=_endereco_bairro,
        endereco_municipio=_endereco_municipio,
        endereco_cod_municipio=codMun,
        endereco_uf=_endereco_uf,
        endereco_cep=_endereco_cep,
        endereco_pais=CODIGO_BRASIL,
        #endereco_telefone='11912341234',
    )

    
    nota_fiscal = NotaFiscal(
        emitente=emitente,
        cliente=cliente,
        uf=emitente.endereco_uf,
        natureza_operacao='VENDA', # venda, compra, transferência, devolução, etc
        forma_pagamento=0,         # 0=Pagamento à vista; 1=Pagamento a prazo; 2=Outros.
        tipo_pagamento=1,
        modelo=55,                 # 55=NF-e; 65=NFC-e
                    # Número do Documento Fiscal.
        data_emissao=datetime.now(),
        data_saida_entrada=datetime.now(),
        tipo_documento=1,          # 0=entrada; 1=saida
        municipio=_municipioIBGE,       # Código IBGE do Município 
        tipo_impressao_danfe=1,    # 0=Sem geração de DANFE;1=DANFE normal, Retrato;2=DANFE normal Paisagem;3=DANFE Simplificado;4=DANFE NFC-e;
        forma_emissao=1,         # 1=Emissão normal (não em contingência);
                    # 0=Normal;1=Consumidor final;
        indicador_intermediador=0,
        finalidade_emissao='1',    # 1=NF-e normal;2=NF-e complementar;3=NF-e de ajuste;4=Devolução de mercadoria.
        processo_emissao='0',      #0=Emissão de NF-e com aplicativo do contribuinte;
        transporte_modalidade_frete=1,
        informacoes_adicionais_interesse_fisco='',
        totais_tributos_aproximado=Decimal(totalTributos(produtos,frete,_tipo_documento)),
        indicador_presencial=2,


        serie='1',
        numero_nf=str(numNota), 
        indicador_destino=(lambda x: 1 if x == emitente.endereco_uf else 2)(_endereco_uf),
        cliente_final=1,
    )
    nota_fiscal.adicionar_responsavel_tecnico(**settings.responsavelTecnico)
    
    def adicionaProdutos(produtos):
        qtdProdutos = 0
        for produto in produtos:
            qtdProdutos += produto["quantity"]
        for produto in produtos:
            _descricao = produto["item"]["title"]
            _codigo = codigoTitulo(_descricao)
            _ncm = ncmTitulo(_descricao)
            if _ncm == "": 
                return False
            _quantidade_comercial=Decimal(produto["quantity"])
            if _endereco_uf != emitente.endereco_uf: _cfop = '6102'
            else: _cfop = "5102" 
            if _tipo_documento == "CPF":
                if semTaxa:
                    _valor_unitario_comercial = Decimal((produto["unit_price"] - frete/qtdProdutos))
                else:
                    _valor_unitario_comercial = Decimal((produto["unit_price"]  - produto["sale_fee"] - frete/qtdProdutos))
            else:
                _valor_unitario_comercial= Decimal(round(produto["unit_price"],2))
            _valor_total_bruto=Decimal(round(_valor_unitario_comercial*_quantidade_comercial, 2))
            _quantidade_tributavel=_quantidade_comercial
            _valor_unitario_tributavel=_valor_unitario_comercial
            _valor_tributos_aprox=str(round(Decimal(0.04)*_valor_unitario_tributavel*_quantidade_tributavel,2))
            nota_fiscal.adicionar_produto_servico(
                codigo=_codigo,                           # id do produto
                descricao=_descricao,
                ncm=_ncm,
                #cest='0100100',                            # NT2015/003
                cfop=_cfop,
                unidade_comercial='UN',
                ean='SEM GTIN',
                ean_tributavel='SEM GTIN',
                quantidade_comercial=_quantidade_comercial,        # 12 unidades
                valor_unitario_comercial=_valor_unitario_comercial,  # preço unitário
                valor_total_bruto=_valor_total_bruto,       # preço total
                unidade_tributavel='UN',
                quantidade_tributavel=_quantidade_tributavel,
                valor_unitario_tributavel=_valor_unitario_tributavel,
                ind_total=1,
                # numero_pedido='12345',                   # xPed
                # numero_item='123456',                    # nItemPed
                icms_modalidade='102',
                icms_origem=0,
                icms_csosn='400',
                pis_modalidade='07',
                cofins_modalidade='07',
                valor_tributos_aprox=_valor_tributos_aprox
            )
        return True
    if adicionaProdutos(produtos) == False:
        return "Erro - Não há um ncm associado ao tipo de produto"
    serializador = SerializacaoXML(_fonte_dados, homologacao=homologacao)
    nfe = serializador.exportar()

    # assinatura
    a1 = AssinaturaA1(certificado, senha)
    xml = a1.assinar(nfe)
    # envio
    con = ComunicacaoSefaz(uf, certificado, senha, homologacao)
    time.sleep(0.01)
    envio = con.autorizacao(modelo='nfe', nota_fiscal=xml,contingencia=False)
    # em caso de sucesso o retorno será o xml autorizado
    # Ps: no modo sincrono, o retorno será o xml completo (<nfeProc> = <NFe> + <protNFe>)
    # no modo async é preciso montar o nfeProc, juntando o retorno com a NFe  
    from lxml import etree
    if envio[0] == 0:
        return (etree.tostring(envio[1], encoding="unicode").replace('\n','').replace('ns0:','').replace(':ns0', ''))
    else:
        _xml = envio[1].text
        erro = _xml.split("xMotivo>")
        contagem = _xml.count("xMotivo")
        return "Erro - " + erro[_xml.count("xMotivo") -1][:-2]

def obterIdVendedor(atoken):
    header = {
        'Authorization' : f'Bearer {atoken}',
    }
    return requests.get("https://api.mercadolibre.com/users/me",headers=header).json()["id"]


def enviarNotaMLB(atoken, nota, idEnvio):
    header = {
        'Authorization' : f'Bearer {atoken}',
        'Content-Type': 'application/xml'
    }
    data=nota
    return requests.post(f"https://api.mercadolibre.com/shipments/{idEnvio}/invoice_data/?siteId=MLB", headers= header, data= data)

def baixarNotasMes(atoken, data, nome, threadProgress):
    header = {
        'Authorization' : f'Bearer {atoken}',
    }
    SellerID = requests.get("https://api.mercadolibre.com/users/me",headers=header).json()["id"]
    
    url = f'http://api.mercadolibre.com/users/{SellerID}/invoices/sites/MLB/batch_request/period/{data}'

    response = requests.get(url, headers= header, verify = False, stream = True)

    file = zipfile.ZipFile(io.BytesIO(response.content))

    name = f"{data}-{nome}"
    with open(f'{name}.zip', 'wb') as f:
        for a in response.iter_content(chunk_size=128):
            f.write(a)

def getShipmentId(atoken, id):
    header = {
        'x-format-new' : 'true',
        'Authorization' : f'Bearer {atoken}'
        
    }
    r = requests.get(f"https://api.mercadolibre.com/orders/{id}", headers=header)
    order = r.json()
    return order["shipping"]["id"]
    
def getShipCost(atoken, id):
    header = {
        'x-format-new' : 'true',
        'Authorization' : f'Bearer {atoken}'
        
    }
    r = requests.get(f"https://api.mercadolibre.com/shipments/{id}/costs", headers=header)
    ship = r.json()
    return ship["senders"][0]["cost"]
def consultaShippingID(atoken, id):
    header = {
        'x-format-new' : 'true',
        'Authorization' : f'Bearer {atoken}'
        
    }
    r = requests.get(f"https://api.mercadolibre.com/shipments/{id}", headers=header)
    ship = r.json()
    if ship["status"] == "ready_to_ship" and ship["substatus"] == "invoice_pending": 
            return True
    else: return False

def getOrderIds(atoken, continuaLoop):
    header = {
        'Authorization' : f'Bearer {atoken}'
    }
    SellerID = requests.get("https://api.mercadolibre.com/users/me",headers=header).json()["id"]
    qItems = 1
    idOrders = {}
    page = 0
    while qItems > page*50:
        r = requests.get(f'https://api.mercadolibre.com/orders/search?seller={SellerID}&order.status=paid&tags=not_delivered&offset={page*50}&limit=50', headers=header)
        page+=1
        orders = r.json()
        qItems = orders['paging']['total']
        for num, order in enumerate(orders["results"]):
            if(consultaShippingID(atoken, order["shipping"]["id"])):
                valor = order["total_amount"]
                idOrders[order["id"]] = [order["buyer"]["nickname"],
                                         f"{valor:.2f}",
                                         order["shipping"]["id"]]
            if not continuaLoop(100*num/qItems): 
                return idOrders
    return idOrders
def getShip(atoken):
    header = {
        'Authorization' : f'Bearer {atoken}'
    }
    SellerID = requests.get("https://api.mercadolibre.com/shipments/",headers=header).json()
    a = SellerID



def geraAccessToken(token):
    url = 'https://api.mercadolibre.com/oauth/token'
    headers = {
        'accept': 'application/json',
        'content-type': 'application/x-www-form-urlencoded'
    }
    data = {
        'grant_type': 'authorization_code',
        'client_id': settings.client_id,
        'client_secret': settings.client_secret,
        'code': f'{token}',
        'redirect_uri': 'https://jeielss.github.io/nfe-mercadolivre'
    }

    response = requests.post(url, headers=headers, data=data)
    return response.json()["access_token"], response.json()["refresh_token"]

def renovarAccessToken(token):
    url = 'https://api.mercadolibre.com/oauth/token'
    headers = {
        'accept': 'application/json',
        'content-type': 'application/x-www-form-urlencoded'
    }
    data = {
        'grant_type': 'refresh_token',
        'client_id': settings.client_id,
        'client_secret': settings.client_secret,
        'refresh_token': f'{token}',
    }

    response = requests.post(url, headers=headers, data=data)
    json = response.json()
    if "message" in json.keys():
        if "invalid" in json["message"]:
            return geraAccessToken(token)
    return response.json()["access_token"], response.json()["refresh_token"]


