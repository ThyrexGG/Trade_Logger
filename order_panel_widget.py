def get_order_panel_html(symbol: str, current_price: float, account_id: str) -> str:
    """
    Returns the HTML, CSS, and JS for the advanced Market Execution DOM panel.
    This component will directly POST to the FastAPI backend to execute trades.
    """
    # Simple bid/ask offset mockup since we don't have true streaming level 2 quotes yet
    bid = round(current_price * 0.9998, 5) if current_price else 0.0
    ask = round(current_price * 1.0002, 5) if current_price else 0.0
    spread = round((ask - bid) * 10000, 1) if current_price else 0.0

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            :root {{
                --bg-dark: #131313;
                --bg-lighter: #1E1E1E;
                --bg-input: #1A1A1A;
                --border-color: #333333;
                --text-main: #FFFFFF;
                --text-muted: #8A99AD;
                --color-sell: #F23645;
                --color-sell-bg: #2A151A;
                --color-sell-hover: #4A1A22;
                --color-buy: #2962FF;
                --color-buy-bg: #15222A;
                --color-buy-hover: #1A354A;
                --color-accent: #00FFCC;
            }}
            body {{
                margin: 0;
                padding: 16px;
                background-color: var(--bg-dark);
                color: var(--text-main);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                font-size: 13px;
                user-select: none;
            }}
            .header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 16px;
            }}
            .symbol-title {{
                font-size: 18px;
                font-weight: 700;
                display: flex;
                align-items: center;
                gap: 8px;
            }}
            .symbol-icon {{
                color: #D97757;
                font-size: 20px;
                font-weight: bold;
            }}
            
            /* Tabs */
            .tabs-container {{
                display: flex;
                background: var(--bg-lighter);
                border-radius: 6px;
                padding: 2px;
                margin-bottom: 16px;
            }}
            .tab-btn {{
                flex: 1;
                padding: 8px 0;
                text-align: center;
                color: var(--text-muted);
                cursor: pointer;
                border-radius: 4px;
                transition: 0.2s;
            }}
            .tab-btn.active {{
                background: #333;
                color: var(--text-main);
                font-weight: 600;
            }}
            
            /* Quote Buttons */
            .quotes-row {{
                display: flex;
                align-items: center;
                margin-bottom: 20px;
            }}
            .quote-btn {{
                flex: 1;
                height: 60px;
                position: relative;
                cursor: pointer;
                border: 1px solid transparent;
                transition: 0.2s;
            }}
            .quote-btn.sell {{
                background: var(--color-sell-bg);
                border-radius: 6px 0 0 6px;
            }}
            .quote-btn.sell.active {{
                background: var(--color-sell-hover);
                border-color: var(--color-sell);
            }}
            .quote-btn.buy {{
                background: var(--color-buy-bg);
                border-radius: 0 6px 6px 0;
            }}
            .quote-btn.buy.active {{
                background: var(--color-buy-hover);
                border-color: var(--color-buy);
            }}
            .spread-badge {{
                width: 36px;
                height: 24px;
                background: #111;
                color: var(--text-muted);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 11px;
                font-weight: bold;
                z-index: 10;
                border: 1px solid var(--border-color);
                border-top: none;
                border-bottom: none;
            }}
            .quote-label {{
                position: absolute;
                top: 8px;
                font-size: 12px;
                font-weight: 600;
            }}
            .quote-price {{
                position: absolute;
                bottom: 8px;
                font-size: 16px;
                font-weight: 700;
            }}
            .quote-btn.sell .quote-label, .quote-btn.sell .quote-price {{ left: 12px; color: var(--color-sell); }}
            .quote-btn.buy .quote-label, .quote-btn.buy .quote-price {{ right: 12px; color: var(--color-buy); }}
            
            /* Order Type Tabs */
            .type-tabs {{
                display: flex;
                border-bottom: 1px solid var(--border-color);
                margin-bottom: 16px;
            }}
            .type-tab {{
                padding: 8px 16px;
                color: var(--text-muted);
                cursor: pointer;
                border-bottom: 2px solid transparent;
            }}
            .type-tab.active {{
                color: var(--text-main);
                font-weight: 600;
                border-bottom-color: var(--text-main);
            }}

            /* Inputs */
            .input-group {{
                margin-bottom: 16px;
            }}
            .input-label {{
                color: var(--text-muted);
                margin-bottom: 6px;
                display: flex;
                align-items: center;
                gap: 4px;
            }}
            .input-box {{
                display: flex;
                align-items: center;
                background: var(--bg-input);
                border: 1px solid var(--border-color);
                border-radius: 4px;
                height: 40px;
                padding: 0 12px;
            }}
            .input-box input {{
                flex: 1;
                background: transparent;
                border: none;
                color: var(--text-main);
                font-size: 14px;
                font-weight: 600;
                outline: none;
            }}
            .input-suffix {{
                color: var(--text-muted);
                font-size: 12px;
                display: flex;
                align-items: center;
                gap: 6px;
                cursor: pointer;
            }}
            
            /* Info Box */
            .info-box {{
                background: var(--bg-lighter);
                padding: 12px;
                border-radius: 6px;
                margin-bottom: 20px;
            }}
            .info-row {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 8px;
            }}
            .info-row:last-child {{ margin-bottom: 0; }}
            .info-label {{ color: var(--text-muted); }}
            .info-val {{ font-weight: 600; }}
            
            /* Accordion */
            .accordion-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                cursor: pointer;
                font-weight: 600;
                font-size: 14px;
                margin-bottom: 12px;
            }}
            
            /* Switch */
            .switch {{
                position: relative;
                display: inline-block;
                width: 36px;
                height: 20px;
            }}
            .switch input {{ opacity: 0; width: 0; height: 0; }}
            .slider {{
                position: absolute;
                cursor: pointer;
                top: 0; left: 0; right: 0; bottom: 0;
                background-color: var(--bg-lighter);
                transition: .2s;
                border-radius: 20px;
                border: 1px solid var(--border-color);
            }}
            .slider:before {{
                position: absolute;
                content: "";
                height: 14px; width: 14px;
                left: 2px; bottom: 2px;
                background-color: var(--text-muted);
                transition: .2s;
                border-radius: 50%;
            }}
            input:checked + .slider {{
                background-color: var(--text-main);
                border-color: var(--text-main);
            }}
            input:checked + .slider:before {{
                transform: translateX(16px);
                background-color: var(--bg-dark);
            }}
            
            /* Submit Button */
            .submit-btn {{
                width: 100%;
                padding: 14px;
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 16px;
                font-weight: 700;
                cursor: pointer;
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 4px;
                margin-top: 10px;
                transition: 0.2s;
            }}
            .submit-btn.sell {{ background-color: var(--color-sell); }}
            .submit-btn.sell:hover {{ background-color: #ff4a58; }}
            .submit-btn.buy {{ background-color: var(--color-buy); }}
            .submit-btn.buy:hover {{ background-color: #3d71ff; }}
            .submit-btn:disabled {{ opacity: 0.6; cursor: not-allowed; }}
            .submit-subtext {{ font-size: 11px; font-weight: 400; opacity: 0.9; }}
            
            /* Status Toast */
            #toast {{
                position: fixed;
                bottom: 20px;
                left: 50%;
                transform: translateX(-50%);
                background: #333;
                color: #fff;
                padding: 8px 16px;
                border-radius: 4px;
                display: none;
                z-index: 1000;
                text-align: center;
                box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            }}
        </style>
    </head>
    <body>
    
        <div class="header">
            <div class="symbol-title">
                <span class="symbol-icon">C</span> {symbol}
            </div>
            <div style="color: var(--text-muted); cursor: pointer;">
                &#10005;
            </div>
        </div>
        
        <div class="tabs-container">
            <div class="tab-btn active" onclick="setMode('Order')">Order</div>
            <div class="tab-btn" onclick="setMode('DOM')">DOM</div>
        </div>
        
        <div class="quotes-row">
            <div class="quote-btn sell active" id="btnSell" onclick="setDirection('Sell')">
                <div class="quote-label">Sell</div>
                <div class="quote-price">{bid}</div>
            </div>
            <div class="spread-badge">{spread}</div>
            <div class="quote-btn buy" id="btnBuy" onclick="setDirection('Buy')">
                <div class="quote-label">Buy</div>
                <div class="quote-price">{ask}</div>
            </div>
        </div>
        
        <div class="type-tabs">
            <div class="type-tab active" onclick="setType('Market', this)">Market</div>
            <div class="type-tab" onclick="setType('Limit', this)">Limit</div>
            <div class="type-tab" onclick="setType('Stop', this)">Stop</div>
        </div>
        
        <div class="input-group">
            <div class="input-label">Price</div>
            <div class="input-box">
                <input type="number" id="inputPrice" value="{bid}" step="0.0001">
                <div class="input-suffix">&#8644; Bid &ndash; 80</div>
            </div>
        </div>
        
        <div class="input-group">
            <div class="input-label">Volume / Lots</div>
            <div class="input-box">
                <input type="number" id="inputVol" value="0.10" step="0.01">
                <div class="input-suffix">&#8644; Vol</div>
            </div>
        </div>
        
        <div class="info-box">
            <div class="info-row">
                <span class="info-label">Account Target</span>
                <span class="info-val">{account_id}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Trade value (200:1)</span>
                <span class="info-val" id="valTrade">--</span>
            </div>
            <div class="info-row">
                <span class="info-label">Pip value</span>
                <span class="info-val" id="valPip">--</span>
            </div>
        </div>
        
        <div class="accordion-header">
            Exits <span>&#8963;</span>
        </div>
        
        <div class="input-group">
            <div class="header" style="margin-bottom: 6px;">
                <div class="input-label" style="margin: 0;">Take profit, price</div>
                <label class="switch">
                  <input type="checkbox" id="chkTP" onchange="toggleTP()">
                  <span class="slider"></span>
                </label>
            </div>
            <div class="input-box" id="boxTP" style="opacity: 0.3; pointer-events: none;">
                <input type="number" id="inputTP" value="" step="0.0001">
                <div class="input-suffix">&#8644; pips</div>
            </div>
        </div>
        
        <div class="input-group">
            <div class="header" style="margin-bottom: 6px;">
                <div class="input-label" style="margin: 0;">Stop loss, price</div>
                <label class="switch">
                  <input type="checkbox" id="chkSL" onchange="toggleSL()">
                  <span class="slider"></span>
                </label>
            </div>
            <div class="input-box" id="boxSL" style="opacity: 0.3; pointer-events: none;">
                <input type="number" id="inputSL" value="" step="0.0001">
                <div class="input-suffix">&#8644; pips</div>
            </div>
        </div>
        
        <button class="submit-btn sell" id="btnSubmit" onclick="executeTrade()">
            <div>Sell</div>
            <div class="submit-subtext" id="submitSubtext">0.1 {symbol} @ {bid} MARKET</div>
        </button>
        
        <div id="toast">Order executing...</div>
        
        <script>
            let state = {{
                direction: 'Sell',
                type: 'Market',
                symbol: '{symbol}',
                accountId: '{account_id}',
                bid: {bid},
                ask: {ask}
            }};
            
            function setDirection(dir) {{
                state.direction = dir;
                document.getElementById('btnSell').classList.toggle('active', dir === 'Sell');
                document.getElementById('btnBuy').classList.toggle('active', dir === 'Buy');
                
                const btnSubmit = document.getElementById('btnSubmit');
                btnSubmit.className = 'submit-btn ' + dir.toLowerCase();
                btnSubmit.children[0].innerText = dir;
                
                if(state.type === 'Market') {{
                    document.getElementById('inputPrice').value = dir === 'Sell' ? state.bid : state.ask;
                }}
                
                updateButtonText();
            }}
            
            function setType(type, el) {{
                state.type = type;
                document.querySelectorAll('.type-tab').forEach(t => t.classList.remove('active'));
                el.classList.add('active');
                updateButtonText();
            }}
            
            function toggleTP() {{
                const checked = document.getElementById('chkTP').checked;
                document.getElementById('boxTP').style.opacity = checked ? '1' : '0.3';
                document.getElementById('boxTP').style.pointerEvents = checked ? 'auto' : 'none';
            }}
            
            function toggleSL() {{
                const checked = document.getElementById('chkSL').checked;
                document.getElementById('boxSL').style.opacity = checked ? '1' : '0.3';
                document.getElementById('boxSL').style.pointerEvents = checked ? 'auto' : 'none';
            }}
            
            function updateButtonText() {{
                const vol = document.getElementById('inputVol').value || '0.1';
                const price = document.getElementById('inputPrice').value || state.bid;
                document.getElementById('submitSubtext').innerText = `${{vol}} ${{state.symbol}} @ ${{price}} ${{state.type.toUpperCase()}}`;
            }}
            
            document.getElementById('inputVol').addEventListener('input', updateButtonText);
            document.getElementById('inputPrice').addEventListener('input', updateButtonText);
            
            function showToast(msg, isError) {{
                const toast = document.getElementById('toast');
                toast.innerText = msg;
                toast.style.background = isError ? 'var(--color-sell)' : 'var(--color-accent)';
                toast.style.color = isError ? '#fff' : '#000';
                toast.style.display = 'block';
                setTimeout(() => toast.style.display = 'none', 3000);
            }}
            
            async function executeTrade() {{
                const btn = document.getElementById('btnSubmit');
                btn.disabled = true;
                btn.children[0].innerText = 'Routing...';
                
                const payload = {{
                    symbol: state.symbol,
                    account_id: state.accountId,
                    direction: state.direction.toUpperCase(),
                    volume: parseFloat(document.getElementById('inputVol').value),
                    order_type: state.type.toUpperCase(),
                    price: parseFloat(document.getElementById('inputPrice').value),
                    stop_loss: document.getElementById('chkSL').checked ? parseFloat(document.getElementById('inputSL').value) : null,
                    take_profit: document.getElementById('chkTP').checked ? parseFloat(document.getElementById('inputTP').value) : null
                }};
                
                try {{
                    const res = await fetch('http://127.0.0.1:8000/api/order/execute', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify(payload)
                    }});
                    
                    const data = await res.json();
                    if(res.ok) {{
                        showToast(data.message || 'Trade executed successfully!', false);
                    }} else {{
                        showToast(data.detail || 'Execution failed', true);
                    }}
                }} catch(e) {{
                    showToast('Network error connecting to API', true);
                }} finally {{
                    btn.disabled = false;
                    btn.children[0].innerText = state.direction;
                }}
            }}
        </script>
    </body>
    </html>
    """
