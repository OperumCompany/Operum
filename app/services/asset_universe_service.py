from app.services.local_storage_service import LocalStorageService
from app.schemas.asset import Asset


class AssetUniverseService:
    def __init__(self):
        self.storage = LocalStorageService()
        self._universe_path = "assets/universe.json"

    def get_all(self) -> list[Asset]:
        data = self.storage.load_json(self._universe_path)
        if data is None:
            self._build_default_universe()
            data = self.storage.load_json(self._universe_path)
        return [Asset(**self._repair_asset_item(item)) for item in data]

    def search(self, query: str) -> list[Asset]:
        q = query.lower().strip()
        if not q or len(q) < 2:
            return []
        return [
            a for a in self.get_all()
            if q in a.ticker.lower() or q in a.name.lower()
        ]

    def get_by_ticker(self, ticker: str) -> Asset | None:
        for a in self.get_all():
            if a.ticker.lower() == ticker.lower():
                return a
        return None

    def _repair_text(self, value: str) -> str:
        repaired = value
        for _ in range(3):
            if not any(marker in repaired for marker in ("Ã", "Â", "â")):
                break
            try:
                next_value = repaired.encode("latin1").decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                break
            if next_value == repaired:
                break
            repaired = next_value
        return repaired

    def _repair_asset_item(self, item: dict) -> dict:
        return {
            key: self._repair_text(value) if isinstance(value, str) else value
            for key, value in item.items()
        }

    def _build_default_universe(self):
        assets = [
            # --- AÃ§Ãµes Brasil (B3) ---
            Asset(ticker="PETR4", name="Petrobras PN", asset_class="BR_STOCK", country="BR", currency="BRL", sector="PetrÃ³leo e GÃ¡s", sub_type="PN"),
            Asset(ticker="PETR3", name="Petrobras ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="PetrÃ³leo e GÃ¡s", sub_type="ON"),
            Asset(ticker="VALE3", name="Vale ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="MineraÃ§Ã£o", sub_type="ON"),
            Asset(ticker="ITUB4", name="ItaÃº Unibanco PN", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Financeiro", sub_type="PN"),
            Asset(ticker="ITUB3", name="ItaÃº Unibanco ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Financeiro", sub_type="ON"),
            Asset(ticker="BBDC4", name="Bradesco PN", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Financeiro", sub_type="PN"),
            Asset(ticker="BBDC3", name="Bradesco ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Financeiro", sub_type="ON"),
            Asset(ticker="BBAS3", name="Banco do Brasil ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Financeiro", sub_type="ON"),
            Asset(ticker="SANB11", name="Santander BR UNIT", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Financeiro", sub_type="UNIT"),
            Asset(ticker="ABEV3", name="Ambev ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Bebidas", sub_type="ON"),
            Asset(ticker="WEGE3", name="WEG ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Equipamentos ElÃ©tricos", sub_type="ON"),
            Asset(ticker="ELET3", name="Eletrobras ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Energia ElÃ©trica", sub_type="ON"),
            Asset(ticker="ELET6", name="Eletrobras PN B", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Energia ElÃ©trica", sub_type="PNB"),
            Asset(ticker="RENT3", name="Localiza ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Aluguel de VeÃ­culos", sub_type="ON"),
            Asset(ticker="LREN3", name="Lojas Renner ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Varejo", sub_type="ON"),
            Asset(ticker="MGLU3", name="Magazine Luiza ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Varejo", sub_type="ON"),
            Asset(ticker="VIIA3", name="Casas Bahia ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Varejo", sub_type="ON"),
            Asset(ticker="AMER3", name="Americanas ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Varejo", sub_type="ON"),
            Asset(ticker="JBSS3", name="JBS ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Alimentos", sub_type="ON"),
            Asset(ticker="MRFG3", name="Marfrig ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Alimentos", sub_type="ON"),
            Asset(ticker="BEEF3", name="Minerva ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Alimentos", sub_type="ON"),
            Asset(ticker="SUZB3", name="Suzano ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Papel e Celulose", sub_type="ON"),
            Asset(ticker="KLBN11", name="Klabin UNIT", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Papel e Celulose", sub_type="UNIT"),
            Asset(ticker="GGBP4", name="Gerdau PN", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Siderurgia", sub_type="PN"),
            Asset(ticker="CSNA3", name="Companhia SiderÃºrgica Nacional ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Siderurgia", sub_type="ON"),
            Asset(ticker="CMIN3", name="CSN MineraÃ§Ã£o ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="MineraÃ§Ã£o", sub_type="ON"),
            Asset(ticker="RAIL3", name="Rumo ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="LogÃ­stica", sub_type="ON"),
            Asset(ticker="CCRO3", name="CCR ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="ConcessÃµes", sub_type="ON"),
            Asset(ticker="ECOR3", name="Ecorodovias ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="ConcessÃµes", sub_type="ON"),
            Asset(ticker="GOLL4", name="Gol PN", asset_class="BR_STOCK", country="BR", currency="BRL", sector="AviaÃ§Ã£o", sub_type="PN"),
            Asset(ticker="AZUL4", name="Azul PN", asset_class="BR_STOCK", country="BR", currency="BRL", sector="AviaÃ§Ã£o", sub_type="PN"),
            Asset(ticker="EMBR3", name="Embraer ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="AeronÃ¡utico", sub_type="ON"),
            Asset(ticker="HAPV3", name="Hapvida ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="SaÃºde", sub_type="ON"),
            Asset(ticker="RDOR3", name="Rede D'Or ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="SaÃºde", sub_type="ON"),
            Asset(ticker="FLRY3", name="Fleury ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="SaÃºde", sub_type="ON"),
            Asset(ticker="QUAL3", name="Qualicorp ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="SaÃºde", sub_type="ON"),
            Asset(ticker="RADL3", name="Raia Drogasil ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="FarmÃ¡cias", sub_type="ON"),
            Asset(ticker="PRIO3", name="Petrorio ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="PetrÃ³leo e GÃ¡s", sub_type="ON"),
            Asset(ticker="CSAN3", name="Cosan ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="LogÃ­stica e Energia", sub_type="ON"),
            Asset(ticker="UGPA3", name="Ultrapar ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="DistribuiÃ§Ã£o", sub_type="ON"),
            Asset(ticker="EQTL3", name="Equatorial ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Energia ElÃ©trica", sub_type="ON"),
            Asset(ticker="NEOE3", name="Neoenergia ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Energia ElÃ©trica", sub_type="ON"),
            Asset(ticker="CPLE6", name="Copel PN B", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Energia ElÃ©trica", sub_type="PNB"),
            Asset(ticker="CMIG4", name="Cemig PN", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Energia ElÃ©trica", sub_type="PN"),
            Asset(ticker="TIMS3", name="Tim ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="TelecomunicaÃ§Ãµes", sub_type="ON"),
            Asset(ticker="VIVT3", name="TelefÃ´nica Brasil ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="TelecomunicaÃ§Ãµes", sub_type="ON"),
            Asset(ticker="CXSE3", name="Caixa Seguridade ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Seguros", sub_type="ON"),
            Asset(ticker="IRBR3", name="IRB Brasil RE ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Seguros", sub_type="ON"),
            Asset(ticker="PSSA3", name="Porto Seguro ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Seguros", sub_type="ON"),
            Asset(ticker="ARZZ3", name="Arezzo ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="CalÃ§ados", sub_type="ON"),
            Asset(ticker="ALPA4", name="Alpargatas PN", asset_class="BR_STOCK", country="BR", currency="BRL", sector="TÃªxtil", sub_type="PN"),
            Asset(ticker="SOMA3", name="Grupo Soma ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="VestuÃ¡rio", sub_type="ON"),
            Asset(ticker="NTCO3", name="Natura ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="CosmÃ©ticos", sub_type="ON"),
            Asset(ticker="CVCB3", name="CVC Brasil ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Turismo", sub_type="ON"),
            Asset(ticker="YDUQ3", name="Yduqs ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="EducaÃ§Ã£o", sub_type="ON"),
            Asset(ticker="COGN3", name="Cogna ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="EducaÃ§Ã£o", sub_type="ON"),
            Asset(ticker="MRVE3", name="MRV ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="ConstruÃ§Ã£o", sub_type="ON"),
            Asset(ticker="CYRE3", name="Cyrela ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="ConstruÃ§Ã£o", sub_type="ON"),
            Asset(ticker="DIRR3", name="Direcional ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="ConstruÃ§Ã£o", sub_type="ON"),
            Asset(ticker="TEND3", name="Tenda ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="ConstruÃ§Ã£o", sub_type="ON"),
            Asset(ticker="EZTC3", name="EZTEC ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="ConstruÃ§Ã£o", sub_type="ON"),
            Asset(ticker="MULT3", name="Multiplan ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Shoppings", sub_type="ON"),
            Asset(ticker="IGTI11", name="Iguatemi UNIT", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Shoppings", sub_type="UNIT"),
            Asset(ticker="BRKM5", name="Braskem PN A", asset_class="BR_STOCK", country="BR", currency="BRL", sector="PetroquÃ­mica", sub_type="PNA"),
            Asset(ticker="UNIP6", name="Unipar PN B", asset_class="BR_STOCK", country="BR", currency="BRL", sector="PetroquÃ­mica", sub_type="PNB"),
            Asset(ticker="TAEE11", name="Taesa UNIT", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Energia ElÃ©trica", sub_type="UNIT"),
            Asset(ticker="TRPL4", name="TransmissÃ£o Paulista PN", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Energia ElÃ©trica", sub_type="PN"),
            Asset(ticker="EGIE3", name="Engie Brasil ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Energia ElÃ©trica", sub_type="ON"),
            Asset(ticker="AURE3", name="Auren ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Energia ElÃ©trica", sub_type="ON"),
            Asset(ticker="ENEV3", name="Eneva ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Energia ElÃ©trica", sub_type="ON"),
            Asset(ticker="B3SA3", name="B3 ON", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Financeiro", sub_type="ON"),
            Asset(ticker="BPAC11", name="BTG Pactual UNIT", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Financeiro", sub_type="UNIT"),
            Asset(ticker="XPBR31", name="XP Inc BDR", asset_class="BR_STOCK", country="BR", currency="BRL", sector="Financeiro", sub_type="BDR"),

            # --- Fundos ImobiliÃ¡rios (FIIs) ---
            Asset(ticker="KNRI11", name="Kinea Renda ImobiliÃ¡ria", asset_class="FII", country="BR", currency="BRL", sector="Lajes Corporativas", sub_type="FII"),
            Asset(ticker="XPLG11", name="XP Log", asset_class="FII", country="BR", currency="BRL", sector="LogÃ­stica", sub_type="FII"),
            Asset(ticker="BRCR11", name="BC Fund", asset_class="FII", country="BR", currency="BRL", sector="Lajes Corporativas", sub_type="FII"),
            Asset(ticker="HGCR11", name="CSHG CrÃ©dito", asset_class="FII", country="BR", currency="BRL", sector="CrÃ©dito", sub_type="FII"),
            Asset(ticker="HGLG11", name="CSHG LogÃ­stica", asset_class="FII", country="BR", currency="BRL", sector="LogÃ­stica", sub_type="FII"),
            Asset(ticker="HSML11", name="HSM", asset_class="FII", country="BR", currency="BRL", sector="Lajes Corporativas", sub_type="FII"),
            Asset(ticker="BTLG11", name="BTG LogÃ­stica", asset_class="FII", country="BR", currency="BRL", sector="LogÃ­stica", sub_type="FII"),
            Asset(ticker="VINO11", name="Vinci Offices", asset_class="FII", country="BR", currency="BRL", sector="Lajes Corporativas", sub_type="FII"),
            Asset(ticker="VISC11", name="Vinci Shopping Centers", asset_class="FII", country="BR", currency="BRL", sector="Shoppings", sub_type="FII"),
            Asset(ticker="MXRF11", name="Maxi Renda", asset_class="FII", country="BR", currency="BRL", sector="HÃ­brido", sub_type="FII"),
            Asset(ticker="KNIP11", name="Kinea Ãndice de PreÃ§os", asset_class="FII", country="BR", currency="BRL", sector="CrÃ©dito", sub_type="FII"),
            Asset(ticker="KNCR11", name="Kinea Rendimentos ImobiliÃ¡rios", asset_class="FII", country="BR", currency="BRL", sector="CrÃ©dito", sub_type="FII"),
            Asset(ticker="CPTS11", name="CapitÃ¢nia Securities II", asset_class="FII", country="BR", currency="BRL", sector="CrÃ©dito", sub_type="FII"),
            Asset(ticker="RCRB11", name="Rio Bravo Renda Corporativa", asset_class="FII", country="BR", currency="BRL", sector="Lajes Corporativas", sub_type="FII"),
            Asset(ticker="PVBI11", name="VBI Prime Properties", asset_class="FII", country="BR", currency="BRL", sector="Lajes Corporativas", sub_type="FII"),
            Asset(ticker="JSRE11", name="JS Real Estate", asset_class="FII", country="BR", currency="BRL", sector="Lajes Corporativas", sub_type="FII"),
            Asset(ticker="RECT11", name="REC Renda", asset_class="FII", country="BR", currency="BRL", sector="HÃ­brido", sub_type="FII"),
            Asset(ticker="GGRC11", name="GGR Covepi", asset_class="FII", country="BR", currency="BRL", sector="Lajes Corporativas", sub_type="FII"),
            Asset(ticker="FIIB11", name="FIIB", asset_class="FII", country="BR", currency="BRL", sector="Lajes Corporativas", sub_type="FII"),
            Asset(ticker="ALZR11", name="Alianza Renda", asset_class="FII", country="BR", currency="BRL", sector="Lajes Corporativas", sub_type="FII"),

            # --- Ações negociadas nos EUA ---
            Asset(ticker="AAPL", name="Apple", asset_class="US_STOCK", country="US", currency="USD", sector="Tecnologia", sub_type="Ação EUA", source="example"),
            Asset(ticker="MSFT", name="Microsoft", asset_class="US_STOCK", country="US", currency="USD", sector="Tecnologia", sub_type="Ação EUA", source="example"),
            Asset(ticker="NVDA", name="NVIDIA", asset_class="US_STOCK", country="US", currency="USD", sector="Tecnologia", sub_type="Ação EUA", source="example"),
            Asset(ticker="GOOGL", name="Alphabet", asset_class="US_STOCK", country="US", currency="USD", sector="Tecnologia", sub_type="Ação EUA", source="example"),
            Asset(ticker="AMZN", name="Amazon", asset_class="US_STOCK", country="US", currency="USD", sector="Consumo", sub_type="Ação EUA", source="example"),
            Asset(ticker="META", name="Meta Platforms", asset_class="US_STOCK", country="US", currency="USD", sector="Tecnologia", sub_type="Ação EUA", source="example"),
            Asset(ticker="TSLA", name="Tesla", asset_class="US_STOCK", country="US", currency="USD", sector="Automotivo", sub_type="Ação EUA", source="example"),
            Asset(ticker="JPM", name="JPMorgan Chase", asset_class="US_STOCK", country="US", currency="USD", sector="Financeiro", sub_type="Ação EUA", source="example"),

            # --- Ativos EUA (BDRs) ---
            Asset(ticker="AAPL34", name="Apple BDR", asset_class="US_STOCK", country="US", currency="USD", sector="Tecnologia", sub_type="BDR"),
            Asset(ticker="MSFT34", name="Microsoft BDR", asset_class="US_STOCK", country="US", currency="USD", sector="Tecnologia", sub_type="BDR"),
            Asset(ticker="GOOG34", name="Alphabet BDR", asset_class="US_STOCK", country="US", currency="USD", sector="Tecnologia", sub_type="BDR"),
            Asset(ticker="AMZO34", name="Amazon BDR", asset_class="US_STOCK", country="US", currency="USD", sector="Tecnologia", sub_type="BDR"),
            Asset(ticker="META34", name="Meta BDR", asset_class="US_STOCK", country="US", currency="USD", sector="Tecnologia", sub_type="BDR"),
            Asset(ticker="TSLA34", name="Tesla BDR", asset_class="US_STOCK", country="US", currency="USD", sector="Automotivo", sub_type="BDR"),
            Asset(ticker="NVDC34", name="NVIDIA BDR", asset_class="US_STOCK", country="US", currency="USD", sector="Tecnologia", sub_type="BDR"),
            Asset(ticker="IVVB11", name="iShares S&P 500 ETF BDR", asset_class="US_STOCK", country="US", currency="USD", sector="Ãndice", sub_type="ETF BDR"),
            Asset(ticker="BIVB39", name="Berkshire Hathaway BDR", asset_class="US_STOCK", country="US", currency="USD", sector="Financeiro", sub_type="BDR"),
            Asset(ticker="JPMC34", name="JPMorgan BDR", asset_class="US_STOCK", country="US", currency="USD", sector="Financeiro", sub_type="BDR"),
            Asset(ticker="DISB34", name="Disney BDR", asset_class="US_STOCK", country="US", currency="USD", sector="Entretenimento", sub_type="BDR"),
            Asset(ticker="NFLX34", name="Netflix BDR", asset_class="US_STOCK", country="US", currency="USD", sector="Entretenimento", sub_type="BDR"),
            Asset(ticker="COCA34", name="Coca-Cola BDR", asset_class="US_STOCK", country="US", currency="USD", sector="Bebidas", sub_type="BDR"),
            Asset(ticker="MCDC34", name="McDonald's BDR", asset_class="US_STOCK", country="US", currency="USD", sector="AlimentaÃ§Ã£o", sub_type="BDR"),
            Asset(ticker="PGCO34", name="Procter & Gamble BDR", asset_class="US_STOCK", country="US", currency="USD", sector="Higiene", sub_type="BDR"),

            # --- Criptomoedas ---
            Asset(ticker="BTC", name="Bitcoin", asset_class="CRYPTO", country="global", currency="USD", sector="Criptomoedas", sub_type="Criptomoeda", source="yfinance"),
            Asset(ticker="ETH", name="Ethereum", asset_class="CRYPTO", country="global", currency="USD", sector="Criptomoedas", sub_type="Criptomoeda", source="yfinance"),
            Asset(ticker="SOL", name="Solana", asset_class="CRYPTO", country="global", currency="USD", sector="Criptomoedas", sub_type="Criptomoeda", source="yfinance"),
            Asset(ticker="BNB", name="BNB", asset_class="CRYPTO", country="global", currency="USD", sector="Criptomoedas", sub_type="Criptomoeda", source="yfinance"),
            Asset(ticker="XRP", name="XRP", asset_class="CRYPTO", country="global", currency="USD", sector="Criptomoedas", sub_type="Criptomoeda", source="yfinance"),
            Asset(ticker="ADA", name="Cardano", asset_class="CRYPTO", country="global", currency="USD", sector="Criptomoedas", sub_type="Criptomoeda", source="yfinance"),
            Asset(ticker="DOT", name="Polkadot", asset_class="CRYPTO", country="global", currency="USD", sector="Criptomoedas", sub_type="Criptomoeda", source="yfinance"),
            Asset(ticker="DOGE", name="Dogecoin", asset_class="CRYPTO", country="global", currency="USD", sector="Criptomoedas", sub_type="Criptomoeda", source="yfinance"),
            Asset(ticker="USDT", name="Tether", asset_class="CRYPTO", country="global", currency="USD", sector="Criptomoedas", sub_type="Stablecoin", source="yfinance"),
            Asset(ticker="USDC", name="USD Coin", asset_class="CRYPTO", country="global", currency="USD", sector="Criptomoedas", sub_type="Stablecoin", source="yfinance"),
            Asset(ticker="AVAX", name="Avalanche", asset_class="CRYPTO", country="global", currency="USD", sector="Criptomoedas", sub_type="Criptomoeda", source="yfinance"),
            Asset(ticker="LINK", name="Chainlink", asset_class="CRYPTO", country="global", currency="USD", sector="Criptomoedas", sub_type="Criptomoeda", source="yfinance"),
            Asset(ticker="MATIC", name="Polygon", asset_class="CRYPTO", country="global", currency="USD", sector="Criptomoedas", sub_type="Criptomoeda", source="yfinance"),
            Asset(ticker="ATOM", name="Cosmos", asset_class="CRYPTO", country="global", currency="USD", sector="Criptomoedas", sub_type="Criptomoeda", source="yfinance"),
            Asset(ticker="LTC", name="Litecoin", asset_class="CRYPTO", country="global", currency="USD", sector="Criptomoedas", sub_type="Criptomoeda", source="yfinance"),

        ]

        data = [a.model_dump() for a in assets]
        self.storage.save_json("assets/universe.json", data)

