# Design: Agro endpoints v1 (fenologia, agua e risco termico)

## Contexto

A API ja possui extracao de series climaticas e satelitais com contratos padronizados em `agro_gee_api/routes/gee.py`, usando:

- catalogo de datasets e variaveis em `agro_gee_api/services/gee_meteo_catalog.py`
- servico de extracao compartilhado em `agro_gee_api/services/gee_meteo_extract.py`
- cliente GEE em `agro_gee_api/services/gee_client.py`

O objetivo e adicionar endpoints de dominio agro para soja, milho e algodao com base em ERA5-Land, cobrindo fenologia, ET0/ETc, balanco hidrico simplificado e risco termico.

## Abordagem aprovada

Abordagem A: engine unica de series diarias.

- Um nucleo comum calcula metricas diarias (GDD, ET0, ETc, bucket hidrico, risco termico).
- Endpoints apenas validam payload, orquestram chamadas e montam resposta.
- Geometrias suportadas em todos os endpoints: `point` e `polygon`.

Racional:

- consistencia numerica entre endpoints
- menor duplicacao
- base clara para evolucao v2 com perfis por cultivar/cliente

## Escopo

### In scope

- endpoints v1 para:
  - estimativa fenologica hibrida (macrofase + subfase)
  - ET0/ETc diario
  - balanco hidrico bucket simples
  - status hidrico consolidado
  - risco termico, geada e calor
- culturas: `soybean`, `corn`, `cotton`
- uso de ERA5-Land como fonte principal
- perfis padrao versionados (`v1_default`) por cultura

### Out of scope

- calibracao regional/cultivar fina
- Penman-Monteith completo
- modelos de runoff/percolacao avancados
- forcar data de colheita como restricao dura

## Endpoints v1

- `POST /agro/phenology/estimate/point`
- `POST /agro/phenology/estimate/polygon`
- `POST /agro/et0-etc/point`
- `POST /agro/et0-etc/polygon`
- `POST /agro/water-balance/simple/point`
- `POST /agro/water-balance/simple/polygon`
- `POST /agro/water-status/point`
- `POST /agro/water-status/polygon`
- `POST /agro/thermal-risk/point`
- `POST /agro/thermal-risk/polygon`

## Contratos (v1)

### Campos comuns de entrada

- `crop`: `soybean | corn | cotton`
- `date_planting` (`YYYY-MM-DD`, UTC)
- `cycle_days` (`int > 0`)
- `date_harvest` (opcional; referencia apenas)
- geometria: `coordinates` (point) ou `geometry` (polygon GeoJSON)
- `profile_version` (opcional; default `v1_default`)

### Campos especificos

- `water-balance` e `water-status`:
  - `cad_mm` (`float > 0`, obrigatorio)
  - `water_initial_pct` (`float` entre `0` e `100`, obrigatorio)

### Convenios de tipos/unidades

- temperatura: `degC`
- agua/evapotranspiracao: `mm/day`
- chuva ERA5 convertida de `m` para `mm`
- datas na resposta: `YYYY-MM-DD`

### Request base (point)

```json
{
  "crop": "soybean",
  "date_planting": "2026-10-15",
  "cycle_days": 125,
  "date_harvest": "2027-02-20",
  "coordinates": [-48.36, -16.67],
  "profile_version": "v1_default"
}
```

### Request base (polygon)

```json
{
  "crop": "corn",
  "date_planting": "2026-10-01",
  "cycle_days": 135,
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[-48.37, -16.68], [-48.35, -16.68], [-48.35, -16.66], [-48.37, -16.66], [-48.37, -16.68]]]
  },
  "profile_version": "v1_default"
}
```

### Response shape por endpoint

- `phenology/estimate`: `current_stage`, `progress`, `stage_transitions[]`, `confidence`, `explanation`
- `et0-etc`: `series[]` com `date`, `et0_mm`, `kc`, `etc_mm`, `macro_stage`, `sub_stage`
- `water-balance/simple`: `series[]` com `date`, `precip_mm`, `et0_mm`, `etc_mm`, `soil_water_mm`, `deficit_mm`, `excess_mm`; `summary`
- `water-status`: `status`, `score`, `metrics`, `explanation`
- `thermal-risk`: `heat`, `cold`, `frost` (cada um com `class`, `score`, `explanation`, `events[]`)

### Erro padrao (exemplo)

```json
{
  "error_code": "INVALID_REQUEST",
  "message": "water_initial_pct must be between 0 and 100",
  "retryable": false,
  "details": {"field": "water_initial_pct"}
}
```

### Saidas principais

- fenologia: `macro_stage`, `sub_stage`, `gdd_accum`, `%cycle`, `stage_transitions[]`
- et0-etc: serie diaria `et0_mm`, `kc`, `etc_mm`, fase do dia
- water-balance: serie diaria `precip_mm`, `et0_mm`, `etc_mm`, `soil_water_mm`, `deficit_mm`, `excess_mm`
- water-status: `status` (`deficit|adequado|excesso`), `score`, `explanation`
- thermal-risk: por risco (`heat|cold|frost`) com `class`, `score`, `explanation` e eventos diarios

## Metodologia de calculo v1

### Convencao de intervalos

- todas as faixas usam `[inicio, fim)`
- ultima faixa de cada eixo fecha em `fim` (`[inicio, fim]`)
- isso evita sobreposicao em bordas (10, 45, 85 etc.)

### 1) Pre-processamento diario (ERA5-Land)

- `tmed_c = temperature_2m(K) - 273.15`
- `tmin_c`, `tmax_c` a partir de variaveis disponiveis na serie diaria
- `precip_mm = total_precipitation(m) * 1000`
- chuva efetiva v1: `effective_rain_mm = precip_mm`

### 2) GDD diario e acumulado

Por cultura:

- `tbase` fixa
- `tcap` (teto) fixa

Formula diaria:

- `gdd_day = max(0, min(tmed_c, tcap) - tbase)`

Acumulo:

- `gdd_accum[d] = sum(gdd_day[0..d])`

### 2.1) Faixas de fase por GDD acumulado (`v1_default`)

#### Soybean

- `VE`: `[0, 120)`
- `V1-Vn`: `[120, 650)`
- `R1-R6`: `[650, 1350)`
- `R7-R8`: `[1350, 1700]`

#### Corn

- `VE`: `[0, 110)`
- `V1-VT`: `[110, 780)`
- `R1-R5`: `[780, 1450)`
- `R6`: `[1450, 1800]`

#### Cotton

- `emergence`: `[0, 160)`
- `square`: `[160, 780)`
- `flowering-boll`: `[780, 1500)`
- `opening`: `[1500, 1900]`

### 3) Componente de progresso por ciclo

- `dap = dias apos plantio`
- `pct_cycle = clamp(dap / cycle_days, 0, 1)`

`date_harvest`, quando presente, e informativa e nao impoe ajuste rigido.

### 4) Estadio fenologico hibrido

- Determinar fase por `%cycle` (faixas por cultura)
- Determinar fase por `gdd_accum` (faixas por cultura)
- Em divergencia, usar a fase mais atrasada (regra conservadora)
- Retornar macrofase e subfase estimada
- `stage_transitions` usa primeira data em que a fase final muda

### 5) ET0 (Hargreaves-Samani)

- `et0_mm_day = 0.0023 * (tmed_c + 17.8) * sqrt(max(tmax_c - tmin_c, 0)) * Ra_mm_eq`

Onde `Ra_mm_eq` e derivado de latitude + dia juliano em equivalente de mm/dia.

### 5.1) Detalhe de `Ra_mm_eq`

- Para `point`, usar latitude do proprio ponto.
- Para `polygon`, usar latitude do centroide do poligono.
- Equacoes FAO-56 para radiacao extraterrestre diaria:
  - `dr = 1 + 0.033 * cos(2 * pi * J / 365)`
  - `delta = 0.409 * sin(2 * pi * J / 365 - 1.39)`
  - `ws = acos(-tan(phi) * tan(delta))`
  - `Ra_MJ = (24 * 60 / pi) * Gsc * dr * (ws * sin(phi) * sin(delta) + cos(phi) * cos(delta) * sin(ws))`
  - `Gsc = 0.0820 MJ m-2 min-1`
- Conversao para equivalente de evaporacao:
  - `Ra_mm_eq = 0.408 * Ra_MJ`

### 6) ETc

- `kc_day` vem da tabela fixa por cultura + macrofase do dia
- `etc_mm_day = et0_mm_day * kc_day`

### 7) Balanco hidrico bucket simples

Estado inicial:

- `soil_water_0 = cad_mm * (water_initial_pct / 100)`

Recorrencia diaria:

- `soil_raw = soil_water_prev + effective_rain_mm - etc_mm_day`
- `soil_water = clamp(soil_raw, 0, cad_mm)`
- `excess_mm = max(0, soil_raw - cad_mm)`
- `deficit_mm = max(0, etc_mm_day - (soil_water_prev + effective_rain_mm))`

### 8) Status hidrico consolidado

Classificacao por persistencia + severidade:

- `soil_ratio = soil_water_mm / cad_mm`
- dia de deficit se `soil_ratio < 0.30`
- dia de excesso se `soil_ratio > 0.95` ou `excess_mm > 0`
- `deficit_freq = dias_deficit / dias_validos`
- `excess_freq = dias_excesso / dias_validos`
- `deficit_intensity = clamp(sum(deficit_mm) / (sum(etc_mm) + 1e-6), 0, 1)`
- `excess_intensity = clamp(sum(excess_mm) / (sum(precip_mm) + 1e-6), 0, 1)`
- `deficit_score = clamp(0.6 * deficit_freq + 0.4 * deficit_intensity, 0, 1)`
- `excess_score = clamp(0.6 * excess_freq + 0.4 * excess_intensity, 0, 1)`
- `score = max(deficit_score, excess_score)`
- status:
  - `deficit` se `deficit_score >= 0.45` e `deficit_score >= excess_score`
  - `excesso` se `excess_score >= 0.45` e `excess_score > deficit_score`
  - `adequado` caso contrario

Saida inclui `score` (0-1) e `explanation`.

### 9) Risco termico, geada e calor

Eventos diarios por cultura/fase:

- `heat_event` se `tmax_c >= heat_threshold`
- `cold_event` se `tmin_c <= cold_threshold`
- `frost_event` se `tmin_c <= frost_threshold`

Persistencia:

- sequencias >= 3 dias aumentam score

Score por risco (heat/cold/frost) no periodo:

- severidade diaria:
  - `sev_heat_d = clamp((tmax_c - heat_threshold) / 6.0, 0, 1)`
  - `sev_cold_d = clamp((cold_threshold - tmin_c) / 6.0, 0, 1)`
  - `sev_frost_d = clamp((frost_threshold - tmin_c) / 4.0, 0, 1)`
- `base_score = media(sev_*_d)` em dias validos
- `persistence_bonus = 0.15` se maior sequencia de evento >= 3 dias; `0.30` se >= 5 dias
- `score = clamp(base_score + persistence_bonus, 0, 1)`

Resposta:

- `class` (`baixo|medio|alto`) + `score` + `explanation`

## Parametros padrao `v1_default`

### Soybean

- `tbase=10`, `tcap=30`
- macrofases (% ciclo): `establishment [0,10)`, `vegetative [10,45)`, `reproductive [45,85)`, `maturation [85,100]`
- subfases: `VE`, `V1-Vn`, `R1-R6`, `R7-R8`
- `kc`: `0.45`, `0.85`, `1.15`, `0.70`
- limiares termicos:
  - calor `>=36` (reprodutivo `>=34`)
  - frio `<=12` (reprodutivo `<=14`)
  - geada `<=2`

### Corn

- `tbase=10`, `tcap=30`
- macrofases (% ciclo): `establishment [0,10)`, `vegetative [10,55)`, `reproductive [55,88)`, `maturation [88,100]`
- subfases: `VE`, `V1-VT`, `R1-R5`, `R6`
- `kc`: `0.40`, `0.90`, `1.20`, `0.75`
- limiares termicos:
  - calor `>=36` (reprodutivo `>=34`)
  - frio `<=10` (reprodutivo `<=12`)
  - geada `<=2`

### Cotton

- `tbase=15`, `tcap=32`
- macrofases (% ciclo): `establishment [0,12)`, `vegetative [12,45)`, `reproductive [45,85)`, `maturation [85,100]`
- subfases: `emergence`, `square`, `flowering-boll`, `opening`
- `kc`: `0.45`, `0.85`, `1.15`, `0.70`
- limiares termicos:
  - calor `>=38` (reprodutivo `>=36`)
  - frio `<=15` (reprodutivo `<=16`)
  - geada `<=2`

### Regras comuns de classe

- classe por score: `baixo < 0.33`, `medio 0.33-0.66`, `alto > 0.66`

## Componentes propostos

- `agro_gee_api/services/agro_engine.py`
  - calculos diarios compartilhados
- `agro_gee_api/services/agro_profiles.py`
  - parametros por cultura/versao
- `agro_gee_api/routes/agro.py`
  - contratos e handlers de dominio agro

## Fluxo de dados

1. Rota valida payload.
2. Rota chama extracao ERA5-Land para serie diaria na geometria.
3. Engine aplica preprocessamento, fenologia hibrida, ET0/ETc, bucket e riscos.
4. Rota monta resposta por endpoint (sem recalcular logica).

## Regra espacial para polygon

- agregacao espacial: media areal dos pixels validos do dia (reducer mean)
- minimo de cobertura valida diaria: `>= 60%` da area alvo
- dia com cobertura abaixo do minimo entra como `no_data_day`
- endpoints retornam `data_completeness` com `valid_days`, `no_data_days`, `valid_ratio`

## Tratamento de erros

- `400 INVALID_REQUEST`: payload/campos invalidos
- `422 NO_DATA`: serie insuficiente para periodo
- `503 GEE_UNAVAILABLE`
- `504 GEE_TIMEOUT`
- `500 INTERNAL_ERROR`

Sem alteracao do envelope de erro atual.

## Estrategia de testes

### Unitarios (engine)

- GDD com casos limite (`tmed<tbase`, `tmed>tcap`)
- ET0 Hargreaves com casos deterministas
- ETc por fase e `kc`
- bucket com clamp, deficit e excesso
- regra conservadora de fase (mais atrasada)

### Contrato (rotas)

- sucesso para `point` e `polygon` em todos endpoints
- validacao de obrigatoriedade/opcionalidade (`date_harvest` opcional)
- validacao de faixas (`water_initial_pct`, `cad_mm`, `cycle_days`)

### Integracao

- mocks de extracao ERA5-Land para cenarios por cultura
- consistencia de agregados e unidades
- nao regressao de rotas existentes em `/gee`

## Criterios de aceite

- resultados deterministas para mesma entrada
- OpenAPI atualizado com exemplos por endpoint
- cobertura de testes unitario + contrato + integracao
- documentacao explicita dos limites do v1

## Riscos e mitigacoes

- Parametros genericos podem divergir de cultivar/regiao.
  - Mitigacao: perfil versionado `v1_default` e caminho de override no v2.
- Sensibilidade de ET0 a qualidade de `tmin/tmax`.
  - Mitigacao: sinalizar dias sem dado suficiente e metricas de completude.
- Risco de sobre-interpretacao agronomica.
  - Mitigacao: explicacoes transparentes e foco em suporte a decisao.

## Compatibilidade e rollout

- Adicao backward-compatible (novo dominio `/agro`)
- Sem mudanca em contratos existentes de `/gee`
- Sem migracoes de banco
