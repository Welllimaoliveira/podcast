# DESAFIO PRF

Resolva as quatro questões antes de olhar o gabarito.

## Questão 1

PRF 2021 - CEBRASPE - Item 29

No modelo de espalhamento dado por p vezes (1 - p), com p entre zero e um, é possível que a taxa de espalhamento de uma notícia ultrapasse 50% por unidade de tempo.

**Certo ou Errado?**

## Questão 2

PRF 2021 - CEBRASPE - Item 30

No mesmo modelo, quanto maior for o número de pessoas que já conhecem uma notícia, maior será necessariamente sua taxa de espalhamento.

**Certo ou Errado?**

## Questão 3

PRF 2021 - CEBRASPE - Item 31

Em uma operação, os totais acumulados de veículos fiscalizados ao fim das cinco primeiras horas foram 20, 60, 120, 200 e 300, mantendo-se o padrão. Nesse caso, ao final da sétima hora o total acumulado será superior a 550 veículos.

**Certo ou Errado?**

## Questão 4

PRF 2021 - CEBRASPE - Item 32

Com os totais acumulados 20, 60, 120, 200 e 300 veículos ao fim das cinco primeiras horas e manutenção do padrão, a quantidade fiscalizada apenas em cada hora forma uma progressão aritmética.

**Certo ou Errado?**

---

# GABARITO

1. ERRADO
2. ERRADO
3. CERTO
4. CERTO

# EXPLICAÇÕES

## Questão 1

Gabarito oficial: **ERRADO**

A questão analisa a função quadrática f(p) = p(1 - p) = -p² + p, que representa a taxa de espalhamento de uma notícia em função da proporção p de pessoas que a conhecem. Para encontrar a taxa máxima, calcula-se o vértice da parábola, dado por p = -b / (2a) = -1 / (2 * (-1)) = 0,5 (ou 50%). Substituindo p = 0,5 na função, obtém-se o valor máximo f(0,5) = 0,5 * (1 - 0,5) = 0,25, ou seja, 25%. A pegadinha está em confundir o ponto de máximo p = 50% com o valor máximo da taxa de espalhamento, que é de no máximo 25%. Como a taxa nunca pode ultrapassar 25%, é impossível atingir mais de 50%. Portanto, a afirmação do item está incorreta, confirmando o gabarito oficial como ERRADO.

## Questão 2

Gabarito oficial: **ERRADO**

A questão aborda o comportamento da função quadrática f(p) = p(1 - p), que descreve a taxa de espalhamento da notícia. Graficamente, essa função é representada por uma parábola com concavidade voltada para baixo. Seu ponto máximo ocorre exatamente em p = 0,5. Isso significa que no intervalo de p = 0 até p = 0,5, a taxa de espalhamento realmente cresce à medida que p aumenta. Contudo, no intervalo de p = 0,5 até p = 1, a função passa a ser estritamente decrescente. A pegadinha é assumir que um crescimento contínuo de pessoas conhecedoras sempre aumentará a taxa. Quando mais da metade da população já conhece a notícia, a taxa de espalhamento diminui. Por ser condicional e não necessária, o gabarito oficial é ERRADO.

## Questão 3

Gabarito oficial: **CERTO**

O item analisa os totais acumulados de veículos fiscalizados: 20, 60, 120, 200 e 300. Para encontrar o padrão, subtrai-se os valores acumulados de cada hora consecutiva: hora 1 (20), hora 2 (60 - 20 = 40), hora 3 (120 - 60 = 60), hora 4 (200 - 120 = 80) e hora 5 (300 - 200 = 100). Observa-se que a cada hora o número de fiscalizados aumenta de 20 em 20. Dando continuidade: na hora 6 serão fiscalizados 120 veículos (acumulado de 300 + 120 = 420) e na hora 7 serão fiscalizados 140 veículos (acumulado de 420 + 140 = 560). Como 560 é superior a 550 veículos, a afirmação está correta. A pegadinha seria calcular erroneamente os acréscimos sem observar a constante. Gabarito CERTO.

## Questão 4

Gabarito oficial: **CERTO**

Para verificar a afirmação, é necessário isolar a quantidade de veículos fiscalizados individualmente em cada hora, calculando a diferença entre os totais acumulados sucessivos. Na primeira hora foram fiscalizados 20 veículos; na segunda hora, 60 - 20 = 40; na terceira hora, 120 - 60 = 60; na quarta hora, 200 - 120 = 80; e na quinta hora, 300 - 200 = 100. A sequência formada por esses valores por hora é (20, 40, 60, 80, 100). Trata-se de uma Progressão Aritmética (PA) de razão igual a 20 e primeiro termo igual a 20, pois a diferença entre termos consecutivos é constante. A pegadinha seria tentar analisar a sequência dos acumulados em vez dos valores individuais por hora. O gabarito é CERTO.
