def get_order_panel_html(symbol: str, current_price: float, account_id: str) -> str:
    """
    Returns the HTML, CSS, and JS for the advanced Market Execution DOM panel.
    This component will directly POST to the FastAPI backend to execute trades.
    """
    bid = round(current_price * 0.9998, 5) if current_price else 0.0
    ask = round(current_price * 1.0002, 5) if current_price else 0.0
    spread = round((ask - bid) * 100, 1) if current_price else 0.0
    
    icon_letter = "M" if "MetaTrader" in account_id else "C"
    icon_color = "#1E88E5" if "MetaTrader" in account_id else "#D97757"

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
                padding: 12px;
                background-color: var(--bg-dark);
                color: var(--text-main);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                font-size: 13px;
                user-select: none;
                overflow-x: hidden;
            }}
            .header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 12px;
            }}
            .symbol-title {{
                font-size: 18px;
                font-weight: 700;
                display: flex;
                align-items: center;
                gap: 8px;
            }}
            .symbol-icon {{
                font-size: 20px;
                font-weight: bold;
            }}
            
            /* Tabs */
            .tabs-container {{
                display: flex;
                background: var(--bg-lighter);
                border-radius: 6px;
                padding: 2px;
                margin-bottom: 12px;
            }}
            .tab-btn {{
                flex: 1;
                padding: 6px 0;
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
                margin-bottom: 16px;
                position: relative;
            }}
            .quote-btn {{
                flex: 1;
                height: 56px;
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
                width: 40px;
                height: 22px;
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
                position: absolute;
                left: 50%;
                transform: translateX(-50%);
            }}
            .quote-label {{
                position: absolute;
                top: 6px;
                font-size: 12px;
                font-weight: 600;
            }}
            .quote-price {{
                position: absolute;
                bottom: 6px;
                font-size: 15px;
                font-weight: 700;
            }}
            .quote-btn.sell .quote-label, .quote-btn.sell .quote-price {{ left: 12px; color: var(--color-sell); }}
            .quote-btn.buy .quote-label, .quote-btn.buy .quote-price {{ right: 12px; color: var(--color-buy); }}
            
            /* Order Type Tabs */
            .type-tabs {{
                display: flex;
                border-bottom: 1px solid var(--border-color);
                margin-bottom: 12px;
            }}
            .type-tab {{
                padding: 6px 16px;
                color: var(--text-muted);
                cursor: pointer;
                border-bottom: 2px solid transparent;
                flex: 1;
                text-align: center;
            }}
            .type-tab.active {{
                color: var(--text-main);
                font-weight: 600;
                border-bottom-color: var(--text-main);
            }}

            /* Inputs */
            .input-group {{
                margin-bottom: 12px;
            }}
            .input-label {{
                color: var(--text-muted);
                margin-bottom: 4px;
                display: flex;
                align-items: center;
                gap: 4px;
                font-size: 12px;
            }}
            .input-box {{
                display: flex;
                align-items: center;
                background: var(--bg-input);
                border: 1px solid var(--border-color);
                border-radius: 4px;
                height: 36px;
                padding: 0 10px;
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
                gap: 4px;
                cursor: pointer;
                white-space: nowrap;
            }}
            
            /* Info Box */
            .info-box {{
                background: var(--bg-lighter);
                padding: 10px;
                border-radius: 6px;
                margin-bottom: 16px;
            }}
            .info-row {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 6px;
                font-size: 12px;
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
                font-size: 13px;
                margin-bottom: 10px;
            }}
            
            /* Switch */
            .switch {{
                position: relative;
                display: inline-block;
                width: 32px;
                height: 18px;
            }}
            .switch input {{ opacity: 0; width: 0; height: 0; }}
            .slider {{
                position: absolute;
                cursor: pointer;
                top: 0; left: 0; right: 0; bottom: 0;
                background: var(--bg-lighter);
                transition: .2s;
                border-radius: 20px;
                border: 1px solid var(--border-color);
            }}
            .slider:before {{
                position: absolute;
                content: "";
                height: 12px; width: 12px;
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
                transform: translateX(14px);
                background-color: var(--bg-dark);
            }}
            
            /* Submit Button & Overlay */
            .submit-btn {{
                width: 100%;
                padding: 12px;
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 16px;
                font-weight: 700;
                cursor: pointer;
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 2px;
                margin-top: 8px;
                margin-bottom: 12px;
                transition: 0.2s;
                position: relative;
                overflow: hidden;
            }}
            .submit-btn.sell {{ background-color: var(--color-sell); }}
            .submit-btn.sell:hover {{ background-color: #ff4a58; }}
            .submit-btn.buy {{ background-color: var(--color-buy); }}
            .submit-btn.buy:hover {{ background-color: #3d71ff; }}
            
            .submit-subtext {{ font-size: 11px; font-weight: 400; opacity: 0.9; text-transform: uppercase; }}
            
            .loading-overlay {{
                position: absolute;
                top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(0,0,0,0.6);
                display: flex;
                align-items: center;
                justify-content: center;
                opacity: 0;
                pointer-events: none;
                transition: 0.2s;
            }}
            .submit-btn.loading .loading-overlay {{
                opacity: 1;
                pointer-events: auto;
            }}
            .spinner {{
                width: 20px;
                height: 20px;
                border: 3px solid rgba(255,255,255,0.3);
                border-radius: 50%;
                border-top-color: #fff;
                animation: spin 1s ease-in-out infinite;
            }}
            @keyframes spin {{ to {{ transform: rotate(360deg); }} }}

            /* DOM View Mockup */
            #domView {{
                display: none;
                text-align: center;
                padding: 40px 0;
                color: var(--text-muted);
            }}
        </style>
    </head>
    <body>
    
        <div class="header">
            <div class="symbol-title">
                <span class="symbol-icon" style="color: {icon_color};">{icon_letter}</span> {symbol}
            </div>
            <div style="color: var(--text-muted); cursor: pointer;">
                &#10005;
            </div>
        </div>
        
        <div class="tabs-container">
            <div class="tab-btn active" id="tabOrder" onclick="setMainMode('Order')">Order</div>
            <div class="tab-btn" id="tabDOM" onclick="setMainMode('DOM')">DOM</div>
        </div>
        
        <div id="domView">
            <div style="font-size: 40px; margin-bottom: 16px;">&#8645;</div>
            <div style="font-size: 16px; font-weight: bold; margin-bottom: 8px;">DOM View</div>
            <div style="font-size: 12px; line-height: 1.5;">Level 2 Market Depth streaming is required for the DOM ladder.</div>
        </div>

        <div id="orderView">
            <div class="quotes-row">
                <div class="quote-btn sell active" id="btnSell" onclick="setDirection('Sell')">
                    <div class="quote-label">Sell</div>
                    <div class="quote-price" id="lblBid">{bid}</div>
                </div>
                <div class="spread-badge">{spread}</div>
                <div class="quote-btn buy" id="btnBuy" onclick="setDirection('Buy')">
                    <div class="quote-label">Buy</div>
                    <div class="quote-price" id="lblAsk">{ask}</div>
                </div>
            </div>
            
            <div class="type-tabs">
                <div class="type-tab active" onclick="setType('Market', this)">Market</div>
                <div class="type-tab" onclick="setType('Limit', this)">Limit</div>
                <div class="type-tab" onclick="setType('Stop', this)">Stop</div>
            </div>
            
            <div class="input-group" id="groupPrice" style="display: none;">
                <div class="input-label">Price</div>
                <div class="input-box">
                    <input type="number" id="inputPrice" value="{bid}" step="0.0001">
                    <div class="input-suffix">&#8644; Bid</div>
                </div>
            </div>
            
            <div class="input-group">
                <div class="input-label">Risk, USD <span style="font-size:10px;">&#8964;</span></div>
                <div class="input-box">
                    <input type="number" id="inputRisk" value="3.28" step="0.01">
                    <div class="input-suffix">&#8644;&nbsp;&nbsp; 1.50 USD <span style="font-size:10px;">&#8964;</span></div>
                </div>
            </div>

            <div class="input-group">
                <div class="input-label" style="display:none;">Volume / Lots</div>
                <div class="input-box">
                    <input type="number" id="inputVol" value="0.10" step="0.01">
                    <div class="input-suffix">&#8644; Vol</div>
                </div>
            </div>
            
            <div class="info-box">
                <div class="info-row">
                    <span class="info-label">Trade value (200:1)</span>
                    <span class="info-val" id="valTrade">299.72 USD</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Available margin</span>
                    <span class="info-val" id="valMargin">294.03 USD</span>
                </div>
                <div class="info-row">
                    <span class="info-label">Pip value</span>
                    <span class="info-val" id="valPip">0.02 USD</span>
                </div>
            </div>
            
            <div class="accordion-header">
                Exits <span>&#8963;</span>
            </div>
            
            <div class="input-group">
                <div class="header" style="margin-bottom: 6px;">
                    <div class="input-label" style="margin: 0;">Take profit, price <span style="font-size:10px;">&#8964;</span></div>
                    <label class="switch">
                      <input type="checkbox" id="chkTP" onchange="toggleTP()">
                      <span class="slider"></span>
                    </label>
                </div>
                <div class="input-box" id="boxTP" style="opacity: 0.3; pointer-events: none;">
                    <input type="number" id="inputTP" value="" step="0.0001">
                    <div class="input-suffix">&#8644;&nbsp;&nbsp; pips <span style="font-size:10px;">&#8964;</span></div>
                </div>
            </div>
            
            <div class="input-group">
                <div class="header" style="margin-bottom: 6px;">
                    <div class="input-label" style="margin: 0;">Stop loss, price <span style="font-size:10px;">&#8964;</span></div>
                    <label class="switch">
                      <input type="checkbox" id="chkSL" onchange="toggleSL()">
                      <span class="slider"></span>
                    </label>
                </div>
                <div class="input-box" id="boxSL" style="opacity: 0.3; pointer-events: none;">
                    <input type="number" id="inputSL" value="" step="0.0001">
                    <div class="input-suffix">&#8644;&nbsp;&nbsp; pips <span style="font-size:10px;">&#8964;</span></div>
                </div>
            </div>

            <div class="info-row" style="margin: 12px 0;">
                <span class="info-label">Risk / Reward</span>
                <span class="info-val">1.1</span>
            </div>
            
            <button class="submit-btn sell" id="btnSubmit" onclick="executeTrade()">
                <div>Sell</div>
                <div class="submit-subtext" id="submitSubtext">300 USD/JPY MARKET</div>
                <div class="loading-overlay"><div class="spinner"></div></div>
            </button>
        </div>
        
        <script>
            let state = {{
                direction: 'Sell',
                type: 'Market',
                symbol: '{symbol}',
                accountId: '{account_id}',
                bid: {bid},
                ask: {ask}
            }};
            
            function setMainMode(mode) {{
                document.getElementById('tabOrder').classList.toggle('active', mode === 'Order');
                document.getElementById('tabDOM').classList.toggle('active', mode === 'DOM');
                document.getElementById('orderView').style.display = mode === 'Order' ? 'block' : 'none';
                document.getElementById('domView').style.display = mode === 'DOM' ? 'block' : 'none';
            }}
            
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
                
                document.getElementById('groupPrice').style.display = type === 'Market' ? 'none' : 'block';
                
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
                let priceText = '';
                if(state.type !== 'Market') {{
                    const price = document.getElementById('inputPrice').value || state.bid;
                    priceText = ` @ ${{price}} ${{state.type.toUpperCase()}}`;
                }} else {{
                    priceText = ' MARKET';
                }}
                // e.g. 300 USD/JPY MARKET or 300 USD/JPY @ 159.976 LIMIT
                // Since user screenshots show volume as a whole number on the button (e.g. 300 instead of 0.1) 
                // we'll multiply volume by 3000 as a mockup of contract sizing, or just display the volume literal
                const mockVolumeDisplay = vol * 3000;
                document.getElementById('submitSubtext').innerText = `${{mockVolumeDisplay}} ${{state.symbol}}${{priceText}}`;
            }}
            
            document.getElementById('inputVol').addEventListener('input', updateButtonText);
            document.getElementById('inputPrice').addEventListener('input', updateButtonText);
            
            // Initialize button text on load
            updateButtonText();
            
            async function executeTrade() {{
                const btn = document.getElementById('btnSubmit');
                btn.classList.add('loading');
                
                const payload = {{
                    symbol: state.symbol,
                    account_id: state.accountId,
                    direction: state.direction.toUpperCase(),
                    volume: parseFloat(document.getElementById('inputVol').value),
                    order_type: state.type.toUpperCase(),
                    price: state.type !== 'Market' ? parseFloat(document.getElementById('inputPrice').value) : null,
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
                        alert(data.message || 'Trade executed successfully!');
                    }} else {{
                        alert('Execution failed: ' + (data.detail || 'Unknown error'));
                    }}
                }} catch(e) {{
                    alert('Network error connecting to API');
                }} finally {{
                    btn.classList.remove('loading');
                }}
            }}
        </script>
    </body>
    </html>
    """
