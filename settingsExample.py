from pynfe.entidades.emitente import Emitente

#Credenciais Mercado Livre - APP
#Dados obtidos ao cadastrar o app na plataforma do mercado livre
client_id= '123456789123456789', 
client_secret= 'codigosecreto123456789123456789'



#Dados para Receita Federal
empresas = {
    "Empresa1":{
        "emitente": Emitente(
            razao_social='Nome da empresa',
            nome_fantasia='Nome fantasia',
            cnpj='123456789123412',           # cnpj apenas números
            codigo_de_regime_tributario='1', # 1 para simples nacional ou 3 para normal
            inscricao_estadual='123456789', # numero de IE da empresa
            #inscricao_municipal='12345',
            cnae_fiscal='1234567',           # cnae apenas números
            endereco_logradouro='Rua dos Bobos',
            endereco_numero='0',
            endereco_bairro='Sem paredes',
            endereco_municipio='Esmero',
            endereco_uf='SN',
            endereco_cep='12345123',
            endereco_pais="1058"
        ),
        "certificado": "endereco_do_certificado.pfx",
        "senha":'senha_do_certifiado',
        "municipioIBGE": "1234567" #codigo IBGE do municipio da empresa 
    },
}

responsavelTecnico = {
    "cnpj":'123456789123412',
    "contato":'Nome do contato',
    "email":'email@email.com',
    "fone":'12123456789'
}
