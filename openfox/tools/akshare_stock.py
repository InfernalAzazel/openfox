from datetime import datetime
from typing import Any, Dict, List, Optional
import akshare as ak
from agno.tools import Toolkit
from agno.utils.log import logger


class AkshareStockTools(Toolkit):
    """基于 AKShare 的股票信息工具集合."""

    def __init__(self) -> None:
        self.ak = ak

        tools: List[Any] = [
            self.get_a_stock_spot,
            self.get_a_stock_hist,
            self.get_stock_info,
            self.get_stock_financial_indicator,
            self.get_a_market_summary,
            self.get_board_industry,
            self.get_board_concept,
            self.get_board_cons,
            self.get_limit_up_pool,
            self.get_market_activity,
        ]
        super().__init__(name="akshare_stock", tools=tools)

    def get_a_stock_spot(self, symbol: Optional[str] = None, source: str = "em", limit: int = 50) -> List[Dict[str, Any]]:
        """获取 A 股实时行情数据.

        封装 `ak.stock_zh_a_spot_em` 和 `ak.stock_zh_a_spot`:

        - 当 `source="em"` 时, 使用东方财富版 `stock_zh_a_spot_em`, 支持沪深京 A 股
        - 当 `source="sina"` 时, 使用新浪版 `stock_zh_a_spot`

        Args:
            symbol: 股票代码, 如 `"000001"`; 为空则返回多只股票
            source: 数据源, `"em"` 或 `"sina"`
            limit: 未指定 `symbol` 时, 返回的前 N 行; `limit<=0` 表示返回全部

        Returns:
            行情列表, 每一项为列名到数值的字典.
        """
        if source not in {"em", "sina"}:
            raise ValueError("source 仅支持 'em' 或 'sina'")

        if source == "em":
            df = self.ak.stock_zh_a_spot_em()
        else:
            df = self.ak.stock_zh_a_spot()

        if symbol:
            # 不同接口字段名略有差异, 常见为: 代码 / 股票代码 / symbol
            col_candidates = ["代码", "股票代码", "symbol"]
            for col in col_candidates:
                if col in df.columns:
                    df = df[df[col].astype(str) == str(symbol)]
                    break
        elif limit > 0:
            df = df.head(limit)

        return df.to_dict(orient="records")

    def get_a_stock_hist(self, symbol: str, period: str = "daily", start_date: str = "20100101", end_date: Optional[str] = None, adjust: str = "") -> List[Dict[str, Any]]:
        """获取 A 股历史行情(日/周/月).

        对应文档接口: `ak.stock_zh_a_hist`
        https://akshare.akfamily.xyz/data/stock/stock.html#id23

        Args:
            symbol: 股票代码, 如 `"000001"`
            period: 周期, `daily` / `weekly` / `monthly`
            start_date: 开始日期, 形如 `"20100101"`
            end_date: 结束日期, 形如 `"20240528"`; 为空则自动取今天
            adjust: 复权方式, `""`(不复权) / `"qfq"`(前复权) / `"hfq"`(后复权)

        Returns:
            历史行情列表, 每一项为一行 K 线数据的字典.
        """
        if end_date is None:
            end_date = datetime.today().strftime("%Y%m%d")

        df = self.ak.stock_zh_a_hist(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
        return df.to_dict(orient="records")

    def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        """获取单只股票的基本信息.

        对应文档接口: `ak.stock_individual_info_em`
        返回结果中的 `item` / `value` 将被整理为一个键值对字典, 便于在对话中展示.

        Args:
            symbol: 股票代码, 如 `"600519"`

        Returns:
            股票信息字典, 例如:

            - `"股票代码"` / `"股票简称"`
            - `"总市值"` / `"流通市值"`
            - `"总股本"` / `"流通股"`
            - `"行业"` / `"上市时间"` 等
        """
        df = self.ak.stock_individual_info_em(symbol=symbol)
        if df is None or df.empty:
            return {}

        try:
            items = df["item"].astype(str).tolist()
            values = df["value"].tolist()
            return dict(zip(items, values))
        except Exception as exc:  # pragma: no cover - 防御性处理
            logger.error(f"解析 stock_individual_info_em 返回数据失败: {exc}")
            return df.to_dict(orient="records")  # 回退为原始列表

    def get_stock_financial_indicator(self, symbol: str, start_year: str = "2020") -> List[Dict[str, Any]]:
        """获取股票财务指标(按年).

        对应文档接口: `ak.stock_financial_analysis_indicator`

        Args:
            symbol: 股票代码, 如 `"600004"`
            start_year: 开始年份, 形如 `"2020"`

        Returns:
            财务指标列表, 每一项为某一期的完整财务指标字典.
        """
        df = self.ak.stock_financial_analysis_indicator(
            symbol=symbol,
            start_year=start_year,
        )
        return df.to_dict(orient="records")

    def get_a_market_summary(self) -> Dict[str, Any]:
        """获取 A 股市场总貌(上交所 + 深交所简要数据封装).

        - 上交所部分: 使用 `ak.stock_sse_summary`
        - 深交所部分: 使用 `ak.stock_szse_summary`, 取最近交易日的汇总

        Returns:
            包含 `sse` 和 `szse` 两个键的字典, 值分别为对应接口返回数据的列表形式.
        """
        result: Dict[str, Any] = {}

        try:
            sse_df = self.ak.stock_sse_summary()
            result["sse"] = sse_df.to_dict(orient="records")
        except Exception as exc:  # pragma: no cover - 外部接口错误
            logger.error(f"获取上交所市场总貌失败: {exc}")
            result["sse_error"] = str(exc)

        try:
            # 深交所需要指定日期, 文档示例使用具体交易日; 这里默认取今天的年月日
            today = datetime.today().strftime("%Y%m%d")
            szse_df = self.ak.stock_szse_summary(date=today)
            result["szse"] = szse_df.to_dict(orient="records")
        except Exception as exc:  # pragma: no cover
            logger.error(f"获取深交所市场总貌失败: {exc}")
            result["szse_error"] = str(exc)

        return result

    def get_board_industry(self, limit: int = 30) -> List[Dict[str, Any]]:
        """获取东方财富行业板块涨跌幅排行.

        用于「识别资金共识」：观察是否有持续领涨的行业，以及行业内的龙头、中军。

        对应接口: `ak.stock_board_industry_name_em`

        Args:
            limit: 返回前 N 个板块，按涨跌幅等排序；<=0 表示全部。

        Returns:
            行业板块列表，每项含板块名称、涨跌幅、领涨股票等字段。
        """
        df = self.ak.stock_board_industry_name_em()
        if limit > 0:
            df = df.head(limit)
        return df.to_dict(orient="records")

    def get_board_concept(self, limit: int = 30) -> List[Dict[str, Any]]:
        """获取东方财富概念板块涨跌幅排行.

        用于「识别资金共识」：观察题材热度与持续性（主线清晰 vs 一日游）。

        对应接口: `ak.stock_board_concept_name_em`

        Args:
            limit: 返回前 N 个板块；<=0 表示全部。

        Returns:
            概念板块列表，每项含板块名称、涨跌幅、领涨股票等字段。
        """
        df = self.ak.stock_board_concept_name_em()
        if limit > 0:
            df = df.head(limit)
        return df.to_dict(orient="records")

    def get_board_cons(
        self,
        board_type: str,
        symbol: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """获取指定行业或概念板块的成分股及涨跌情况.

        用于在第二步锁定主线后，查看板块内龙头、中军、跟风梯队。

        对应接口: `ak.stock_board_industry_cons_em` / `ak.stock_board_concept_cons_em`

        Args:
            board_type: 板块类型，`"industry"`（行业）或 `"concept"`（概念）。
            symbol: 板块名称，如 `"银行"`、`"人工智能"`，需与排行接口返回的名称一致。
            limit: 返回前 N 只成分股；<=0 表示全部。

        Returns:
            成分股列表，每项含代码、名称、涨跌幅、最新价等。
        """
        if board_type not in ("industry", "concept"):
            raise ValueError('board_type 仅支持 "industry" 或 "concept"')
        if board_type == "industry":
            df = self.ak.stock_board_industry_cons_em(symbol=symbol)
        else:
            df = self.ak.stock_board_concept_cons_em(symbol=symbol)
        if df is None or df.empty:
            return []
        if limit > 0:
            df = df.head(limit)
        return df.to_dict(orient="records")

    def get_limit_up_pool(self, date: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取指定日期的涨停股池（为空则取当日）.

        用于判断市场情绪与连板高度（退潮时涨停家数锐减、连板高度被压制）。

        对应接口: `ak.stock_zt_pool_em`

        Args:
            date: 日期，格式 `"YYYYMMDD"`。为空则取当日涨停池。

        Returns:
            涨停股列表，含代码、名称、涨跌幅、连板数、封板时间、所属行业等。
        """
        if not date:
            date = datetime.today().strftime("%Y%m%d")
        df = self.ak.stock_zt_pool_em(date=date)
        if df is None or df.empty:
            return []
        return df.to_dict(orient="records")

    def get_market_activity(self) -> List[Dict[str, Any]]:
        """获取市场赚钱效应数据（涨停家数、跌停家数等）.

        用于第一步判断是否处于「退潮亏钱期」（涨停家数锐减、跌停增多）。

        对应接口: `ak.stock_market_activity_legu`

        Returns:
            赚钱效应统计列表，每项含涨停家数、跌停家数、真实涨停、ST 涨停等字段。
        """
        try:
            df = self.ak.stock_market_activity_legu()
            if df is None or df.empty:
                return []
            return df.to_dict(orient="records")
        except Exception as exc:  # pragma: no cover
            logger.error(f"获取市场赚钱效应数据失败: {exc}")
            return []
