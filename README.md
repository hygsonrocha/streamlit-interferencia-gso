# Simulação de interferência agregada de estações de TV digital em satélites GSO

## Objetivo

Este aplicativo tem como objetivo realizar uma **estimativa da interferência agregada** produzida por estações de TV digital em um **satélite geoestacionário (GSO)**, com foco no sentido **Terra → espaço**.

O app permite:

- editar ou carregar uma lista de estações de radiodifusão;
- configurar parâmetros técnicos da estação modelo e do satélite GSO;
- calcular a interferência por estação;
- agregar as contribuições visíveis;
- analisar o atendimento a um critério de proteção;
- realizar varredura da longitude orbital do satélite GSO;
- visualizar diagramas das antenas adotadas no estudo.

---

## Escopo do estudo

O aplicativo foi desenvolvido como uma ferramenta de **triagem técnica e análise exploratória**, útil para avaliar a ordem de grandeza da interferência e a sensibilidade dos resultados a parâmetros como:

- potência da estação de TV;
- ganho da antena transmissora;
- tilt;
- perdas de linha;
- ganho máximo da antena receptora do satélite;
- longitude orbital do GSO;
- conjunto e localização das estações consideradas.

O modelo atual está voltado ao caso de **interferência agregada cocanal** de estações terrestres em um receptor espacial GSO.

---

## Estrutura lógica do cálculo

Para cada estação de TV, o app executa os seguintes passos principais:

1. calcula a potência na entrada da antena transmissora;
2. calcula a posição da estação e do satélite em coordenadas espaciais;
3. determina a geometria estação–satélite:
   - distância inclinada;
   - azimute;
   - elevação;
4. estima o ganho da antena de TV na direção do satélite, com base em um modelo analítico vertical por elemento e arranjo;
5. estima o ganho da antena receptora do satélite em função do off-axis, com base em um envelope simplificado inspirado na ITU-R S.672-4;
6. calcula a perda de espaço livre, com possibilidade de incluir uma perda adicional simplificada em baixa elevação;
7. calcula a densidade espectral de potência interferente na entrada do receptor do satélite;
8. integra essa densidade na banda efetivamente sobreposta entre o transmissor e o receptor;
9. calcula o ruído térmico na banda do receptor, a relação $I/N$ e a grandeza equivalente $\Delta T/T$;
10. soma as contribuições das estações visíveis para obter o agregado.

---

## Modelos de antena adotados

### Antena TX terrestre

O padrão vertical da antena transmissora é representado por:

$$
E_{TX}(\theta) = E_{elem}(\theta)\,AF_N(\theta)
$$

com:

$$
E_{elem}(\theta)=|\cos(\theta)|^q
$$

e

$$
AF_N(\theta)=\left|\frac{1}{W}\sum_{m=0}^{N-1} w_m\,e^{j m\left(2\pi d_{\lambda}\sin(\theta)+\beta\right)}\right|
$$

onde $N$ é o número de níveis, $d_{\lambda}$ é o espaçamento vertical em comprimentos de onda, $w_m$ são os pesos de amplitude, $\beta$ representa o tilt elétrico e $W=\sum_m w_m$.

No projeto, o parâmetro $q$ é calibrado para reproduzir a HPBW vertical de 1 nível do datasheet, e o arranjo com $N=1,2,4,6$ níveis é ajustado para aproximar as larguras de feixe de referência.

### Antena RX do satélite GSO

O padrão RX do satélite é modelado por um envelope simplificado inspirado na Recomendação ITU-R S.672-4 para feixe circular simples. O ganho é função do ângulo off-axis $\psi$ e do ganho máximo $G_{max}$.

Quando $\psi_b$ não é informado explicitamente, ele é estimado a partir de $G_{max}$ e da eficiência de abertura $\eta_{ap}$ por:

$$
\psi_b \approx 36\pi\sqrt{\eta_{ap}}\,10^{-G_{max}/20}
$$

com $\psi_b$ em graus e $G_{max}$ em dBi.

A partir disso, o ganho RX é obtido por uma lei por trechos em função de $\psi$, com parâmetros $L_N$ e $L_F$ que controlam o platô lateral e o piso de lóbulos distantes do envelope adotado.

---

## Principais grandezas calculadas

### Potência na antena transmissora

A potência efetivamente entregue à antena transmissora é:

$$
P_{ant} = P_{tx} - L_{tx}
$$

onde:

- $P_{tx}$ é a potência do transmissor;
- $L_{tx}$ representa as perdas de linha e perdas acessórias.

---

### ERP máxima da estação modelo

A ERP máxima da estação modelo é calculada como:

$$
ERP_{max} = P_{ant} + G_{t,max}
$$

onde:

- $P_{ant}$ está em dBW;
- $G_{t,max}$ está em dBd.

O valor também é apresentado em kW.

---

### Ganho da antena de TV na direção do satélite

O ganho transmissor na direção do satélite é calculado a partir de:

- ganho máximo da antena;
- discriminação horizontal adicional;
- modelo analítico vertical adotado no estudo.

No app, esse ganho aparece como:

- **ganho na direção do satélite [dBd]**
- e, indiretamente, por meio da **ERP na direção do satélite**.

---

### ERP e EIRP na direção do satélite

As grandezas direcionais exibidas no app são:

$$
ERP_{dir} = P_{ant} + G_{t,dir(dBd)}
$$

$$
EIRP_{dir} = P_{ant} + G_{t,dir(dBi)}
$$

Esses valores representam o nível efetivamente irradiado na direção do satélite GSO analisado.

---

### Perda de espaço livre

A perda de espaço livre é calculada por:

$$
L_{fs} = 32,45 + 20\log_{10}(f_{MHz}) + 20\log_{10}(d_{km})
$$

onde:

- $f$ é a frequência em MHz;
- $d$ é a distância inclinada em km.

---

### Potência interferente no satélite

A potência interferente recebida no satélite é obtida em duas etapas.

Primeiro, calcula-se a densidade espectral de e.i.r.p. do transmissor na direção do satélite:

$$
EIRP_0 = EIRP_{dir} - 10\log_{10}(B_{tx})
$$

Em seguida, calcula-se a densidade espectral interferente na entrada do receptor do satélite:

$$
I_0 = EIRP_0 - L_{path} + G_r - L_{pol} - L_{rx}
$$

onde:

- $L_{path}$ inclui a perda de espaço livre e, quando habilitado no modelo, uma perda adicional simplificada em baixa elevação;
- $G_r$ é o ganho da antena receptora do satélite;
- $L_{pol}$ representa a perda de polarização;
- $L_{rx}$ representa perdas no receptor do satélite.

Por fim, a potência interferente efetiva é obtida integrando essa densidade na banda efetivamente sobreposta:

$$
B_{ov} = \min(B_{tx}, B_{rx})
$$

$$
I = I_0 + 10\log_{10}(B_{ov})
$$

---

### Ruído do receptor

O ruído térmico é calculado por:

$$
N = -228,6 + 10\log_{10}(T_{sys}) + 10\log_{10}(B_{rx})
$$

onde:

- $T_{sys}$ é a temperatura de ruído do sistema;
- $B_{rx}$ é a largura de banda do receptor do satélite.

Assim, o ruído é sempre associado à banda em que o receptor integra a potência de ruído.

---

## Interpretação de $I/N$ em termos de densidade de potência

Em uma conversa técnica sobre o modelo, foi levantada a dúvida se a largura de banda do canal do satélite poderia ser diferente da largura de banda do sinal interferente, e se isso poderia alterar significativamente os resultados.

A formulação mais consistente é trabalhar com:

- densidade espectral de potência interferente;
- densidade espectral de ruído;
- banda efetivamente sobreposta entre o transmissor e o receptor.

Em termos conceituais, pode-se definir:

$$
i = \frac{I}{B_{ov}}
$$

$$
n_0 = \frac{N}{B_{rx}}
$$

ou, equivalentemente, trabalhar com as densidades espectrais $I_0$ e $N_0$.

No caso geral, a relação entre potência interferente e ruído é:

$$
\frac{I}{N} = \frac{I_0}{N_0} \cdot \frac{B_{ov}}{B_{rx}}
$$

Portanto, a igualdade direta entre $I/N$ e $I_0/N_0$ só vale quando a banda efetivamente sobreposta coincide com a banda do receptor.

Na simplificação cocanal homogênea em que:

$$
B_{tx} = B_{rx}
$$

tem-se também:

$$
B_{ov} = B_{rx}
$$

e, nesse caso, a análise se reduz naturalmente ao caso mais simples.

---

### Relação I/N

A relação interferência-ruído é:

$$
I/N = I - N
$$

em dB.

---

### Relação com $\Delta T/T$

A relação equivalente em porcentagem é:

$$
\Delta T/T = 100 \cdot 10^{(I/N)/10}
$$

Essa grandeza também é exibida no app.

---

## Agregação das contribuições

As contribuições das estações consideradas visíveis são somadas em unidade linear:

$$
I_{agg} = \sum_i I_i
$$

Em seguida, o valor é convertido para dBW e comparado com o ruído para calcular o $I/N$ agregado.

O app apresenta:

- resultados por estação;
- resumo agregado por frequência;
- resumo agregado total.

---

## Hipóteses adotadas

O modelo atual utiliza as seguintes hipóteses principais:

- satélite **GSO ideal**;
- análise **estática** por geometria;
- foco em **interferência agregada cocanal**;
- ganho da antena de TV estimado a partir de um modelo analítico vertical com fator de elemento e fator de arranjo calibrado pelos valores de HPBW do datasheet;
- ganho RX do satélite obtido por um envelope simplificado inspirado na Recomendação ITU-R S.672-4, com $\psi_b$ explícito ou calculado a partir de $G_{max}$ e $\eta_{ap}$;
- polarização representada por uma **perda global de mismatch**;
- possibilidade de aplicar uma **perda adicional em baixa elevação**;
- cálculo da interferência a partir da densidade espectral de potência interferente integrada na banda efetivamente sobreposta;
- cálculo de ruído na banda do receptor.

---

## Limitações do modelo

Este aplicativo é uma ferramenta de **estudo preliminar** e, portanto, possui limitações importantes.

### 1. Não modela explicitamente polarizações H e V separadas

O efeito de polarização é tratado de forma simplificada por uma perda global de descasamento. O modelo não separa explicitamente as componentes horizontal e vertical na transmissão e na recepção.

### 2. Não usa, por enquanto, diagrama horizontal detalhado da antena de TV

O ganho transmissor é obtido a partir do ganho máximo da antena, de uma discriminação horizontal adicional e de um modelo analítico vertical da forma $E_{TX}(\theta)=E_{elem}(\theta)AF_N(\theta)$, calibrado pelos valores de HPBW do datasheet. Assim, o modelo ainda não representa explicitamente um diagrama horizontal detalhado da antena real da estação.

### 3. O agregado total só é estritamente cocanal se todas as estações estiverem na mesma frequência

Se o usuário inserir estações com múltiplas frequências, o app avisa que o resumo agregado total deixa de representar um cenário estritamente cocanal.

### 4. O modelo de antena do satélite é simplificado

O ganho RX do satélite é obtido por um envelope analítico em função do ângulo off-axis, inspirado na Recomendação ITU-R S.672-4. O parâmetro $\psi_b$ pode ser fornecido diretamente ou calculado a partir de $G_{max}$ e $\eta_{ap}$. Ainda assim, trata-se de uma representação simplificada do comportamento da antena receptora do satélite no contexto deste estudo preliminar.

### 5. O resultado não deve ser interpretado como conclusão regulatória definitiva

Os resultados são úteis para triagem, comparação entre cenários e entendimento de sensibilidade, mas não substituem uma análise regulatória completa.

---

## Como usar o aplicativo

### 1. Parâmetros da estação de TV

Na barra lateral esquerda, o usuário pode ajustar:

- altitude do local;
- altura da antena;
- potência do transmissor;
- ganho máximo da antena;
- tilt;
- perdas adicionais;
- perdas de linha;
- banda do sistema;
- discriminação horizontal adicional.

Esses parâmetros definem a **estação modelo** usada para expandir as estações da lista.

---

### 2. Parâmetros do satélite GSO

Também na barra lateral, o usuário pode ajustar:

- identificação do satélite;
- longitude orbital GSO;
- temperatura de ruído;
- largura de banda;
- perdas RX;
- ganho máximo RX;
- semi-largura de feixe;
- benchmark de proteção;
- elevação mínima adotada;
- opção de perda extra em baixa elevação.

---

### 3. Lista de estações

Na área principal, o usuário pode:

- editar diretamente a lista de estações;
- inserir novas linhas;
- remover linhas;
- carregar um CSV com estações;
- restaurar as estações padrão;
- baixar um template CSV.

As colunas esperadas são:

- `municipio`
- `uf`
- `latitude_deg`
- `longitude_deg`
- `frequencia_MHz`

---

### 4. Aba “Cenário único”

Nesta aba, o usuário roda a simulação principal do cenário escolhido.

O app apresenta:

- número de estações visíveis;
- interferência agregada total;
- $I/N$ agregado;
- indicação visual de atendimento ou não ao benchmark;
- tabela de resultados por estação;
- resumo agregado por frequência;
- resumo agregado total;
- gráficos auxiliares.

---

### 5. Aba “Varredura de longitude GSO”

Nesta aba, o usuário pode:

- definir a faixa de longitude orbital a ser testada;
- definir o passo da varredura;
- definir uma lista de ganhos RX máximos do satélite.

O app então calcula, para cada longitude e para cada ganho RX máximo:

- o número de estações visíveis;
- a interferência agregada total;
- o $I/N$ agregado;
- o atendimento ao critério.

Além disso, o app identifica automaticamente **faixas contíguas de longitude** que atendem ao critério ($I/N \leq -12{,}2\ \text{dB}$).

---

### 6. Aba “Diagramas das antenas”

Nesta aba, o usuário visualiza:

#### Antena de TV
- diagrama em **escala linear**
- diagrama em **dB**

#### Antena do satélite GSO
- diagrama em **escala linear**
- diagrama em **dB**
- indicação do valor de $\psi_b$ efetivamente usado no modelo
- indicação do valor de $\psi_b$ efetivamente usado no modelo

Se o cenário único já tiver sido rodado, os gráficos também mostram os **pontos correspondentes às estações visíveis** sobre as curvas dos diagramas.

---

## Interpretação prática dos resultados

### Resultados por estação

Mostram, para cada estação:

- geometria;
- ganho transmissor na direção do satélite;
- ERP na direção do satélite;
- potência interferente no satélite;
- ruído;
- $I/N$;
- observação sobre visibilidade.

### Resumo agregado por frequência

Permite avaliar o agregado por grupo de frequência.

### Resumo agregado total

Permite avaliar o agregado do conjunto considerado, lembrando que ele é estritamente cocanal apenas quando todas as estações estão na mesma frequência.

---

## Observações finais

Este app foi construído para apoiar estudos preliminares de interferência agregada entre estações de TV digital e satélites GSO.

Ele é especialmente útil para:

- testar cenários;
- entender sensibilidade dos resultados;
- comparar efeitos de parâmetros técnicos;
- apoiar discussões técnicas exploratórias.

Ele não substitui, por si só, uma análise regulatória completa ou um estudo formal de coordenação.