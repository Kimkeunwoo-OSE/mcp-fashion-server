"""Order recording panel."""
from __future__ import annotations

import streamlit as st

from v5_trader.core.data_engine.database import DatabaseManager
from v5_trader.core.data_engine.schemas import OrderCreate
from v5_trader.core.utils.config import Settings


def render_order_form(db: DatabaseManager) -> None:
    st.subheader("Manual Order Log")
    with st.form("order_form"):
        symbol = st.text_input("Symbol", value="005930.KS")
        side = st.selectbox("Side", options=["BUY", "SELL"])
        quantity = st.number_input("Quantity", min_value=1.0, step=1.0)
        price = st.number_input("Price", min_value=0.0, step=1.0)
        note = st.text_area("Note", placeholder="Optional notes about the trade")
        submitted = st.form_submit_button("Record Order")
        if submitted:
            order = OrderCreate(symbol=symbol, side=side, quantity=quantity, price=price, note=note or None)
            saved = db.record_order(
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=order.price,
                note=order.note,
            )
            st.success(f"Order recorded with id {saved.id}")
