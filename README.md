# App Streamlit - Interferência agregada em satélite GSO

## Como rodar

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Estrutura

- `app.py`: interface Streamlit
- `config/defaults.py`: parâmetros padrão e estações de exemplo
- `core/geometry.py`: geometria ECEF/ENU
- `core/antenna.py`: diagrama RX GSO (ITU-R S.672-4) e perda extra em baixa elevação
- `core/budget.py`: cálculo individual por estação
- `core/aggregate.py`: agregação por frequência e total
- `core/sweep.py`: varredura de longitude orbital GSO

## Observação

O app reutiliza a lógica dos scripts fornecidos, reorganizada em módulos para facilitar manutenção e interface.
