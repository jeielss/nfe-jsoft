# Emissor de Notas Fiscal para Mercado Livre
Essa solução é capaz de obter dados de venda da plataforma Mercado Livre, emitir as notas fiscais para cada uma delas e envia-las de volta a plataforma. O diferencial dessa solução dos softwares já existentes, é que ela é capaz de preencher parâmetros (no momento apenas o NCM, mas expansível para quaisquer) da nota fiscal apenas por palavras no título do produto na plataforma, não sendo necessário a criação de cadastro para cada um dos itens vendidos.

## Configuração

Para configurar o software são necessários os seguintes passos:
- Obter o certificado digital para gerar notas ficais
- Cadastrar o app e obter as credenciais na plataforma do Mercado Livre
- Autorizar o app para obter acesso a conta do Mercado Livre
- Inserir o token no arquivo data/tokensExample e renomea-lo para data/tokens
- Configurar o arquivo settingsExample.py e renomea-lo para settings.py
- Configurar o arquivo data/ncmPalavrachave com o NCM do produto e as palavras-chave que devem estar no título para corresponder ao parâmetro
