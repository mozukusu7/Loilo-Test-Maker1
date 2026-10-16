import streamlit as st
import pandas as pd
import json
import io
import google.generativeai as genai

# ページ基本設定（iPad画面に最適化）
st.set_page_config(
    page_title="ロイロノート用テスト作成アシスタント",
    page_icon="📝",
    layout="wide"
)

st.title("📝 ロイロノート用テスト作成アシスタント")
st.caption("iPadで撮影した問題画像から、ロイロノートに直接インポートできるCSVテストを作成します。")

# サイドバー: APIキー設定
with st.sidebar:
    st.header("⚙️ 設定")
    api_key = st.text_input("Gemini API Key", type="password", help="Google AI Studioで取得したAPIキーを入力してください。")
    st.markdown("---")
    st.markdown("### 📌 適用中のルール")
    st.markdown("- **数式表示**: `[$ ... ]` (LaTeX表記)")
    st.markdown("- **虫食い表示**: `\\operatorname{\\mathrm{\\lower{0.1ex}{\\Box}}}`")
    st.markdown("- **数式問題**: 解答欄の日本語を完全排除")
    st.markdown("- **選択問題**: `radio` (単一選択)形式")

if not api_key:
    st.warning("👈 サイドバーに Gemini API キーを入力してください。")
    st.stop()

genai.configure(api_key=api_key)

# メイン画面 layout
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. 画像の準備")
    uploaded_file = st.file_uploader("問題の写真を撮影または選択してください", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        st.image(uploaded_file, caption="アップロードされた問題画像", use_column_width=True)

with col2:
    st.subheader("2. 生成オプション設定")
    mode = st.radio("作成モード", ["同じ問題（そのままデータ化）", "類題作成（数値・設定変更）"])
    num_questions = st.number_input("作成問題数", min_value=1, max_value=30, value=10)
    
    generate_btn = st.button("🚀 テストカード生成", type="primary", use_container_width=True)

# システムプロンプト定義
SYSTEM_PROMPT = f"""
あなたはロイロノート・スクール用のテスト作成プロフェッショナルです。
与えられた問題画像から、指定された条件でテストを作成し、厳密なJSON形式で出力してください。

【生成条件】
1. モード: {mode}
2. 問題数: 正確に {num_questions} 問作成してください。

【必須ルール】
1. 問題形式の判定:
   - 数値・数式で答える問題: "short:math"
   - 比較・記号・文章から選ぶ問題: "radio"
2. 数式表記:
   - 全すべての数式・数値式は `[$ ... ]` で囲むこと（例: `[$ 4 : 9 = 20 : x ]`）。
   - パーセント記号は `\\％` と表記。
   - 範囲記号（〜）は `\\sim` と表記。
3. 四角・虫食い（□）の表記:
   - 問題文テキスト中: 全角の `□` を使用。
   - 数式 `[$ ... ]` 内: `\\operatorname{{\\mathrm{{\\lower{{0.1ex}}{{\\Box}}}}}}` を使用（例: `[$ \\left(42-\\operatorname{{\\mathrm{{\\lower{{0.1ex}}{{\\Box}}}}}}\\right)\\times24=336 ]`）。
4. 解答欄（"short:math" の場合）:
   - 生徒が数式入力モードで回答するため、日本語（ひらがな・漢字・カタカナ）を絶対に含めないこと。
   - 数値、英字、半角記号のみで記述すること（例: `28`）。
5. 選択問題（"radio" の場合）:
   - 正解には選択肢番号（1, 2, 3...）を文字列で指定すること。
   - 選択肢（options）には日本語を含めて良い。
6. 配点:
   - 全 {num_questions} 問で合計100点満点になるように調整すること。

【出力JSONフォーマット】
以下のキーを持つJSONオブジェクトの配列（JSONのみ）で出力してください。
[
  {{
    "type": "short:math" または "radio",
    "question": "問題文",
    "score": 10,
    "correct": "正解の選択肢番号(radioの場合)または空白",
    "explanation": "解説文",
    "choices": ["正解の数値", "別解数値など"] (short:mathの場合) または ["選択肢1", "選択肢2"...] (radioの場合)
  }}
]
"""

if generate_btn and uploaded_file:
    with st.spinner("AIが画像を解析し、ロイロノート用テストを作成中..."):
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            image_bytes = uploaded_file.getvalue()
            
            response = model.generate_content([
                SYSTEM_PROMPT,
                {"mime_type": uploaded_file.type, "data": image_bytes}
            ])
            
            # レスポンスからJSON抽出
            raw_text = response.text.strip()
            if "```json" in raw_text:
                json_str = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                json_str = raw_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = raw_text
                
            questions = json.loads(json_str)
            st.success("🎉 テストデータの生成が完了しました！")
            
            # CSV変換処理
            csv_lines = ["v1.2.0,,,,,,,", "問題形式,問題文,解答必須,配点,正解の選択肢,解説,選択肢1,選択肢2,選択肢3,選択肢4"]
            
            for q in questions:
                q_type = q.get("type", "short:math")
                q_text = f'"{q.get("question", "")}"'
                q_req = 1
                q_score = q.get("score", 10)
                q_correct = f'"{q.get("correct", "")}"' if q.get("correct") else ""
                q_exp = f'"{q.get("explanation", "")}"'
                
                choices = q.get("choices", [])
                choice_cols = [f'"{c}"' for c in choices]
                
                row = [q_type, q_text, str(q_req), str(q_score), str(q_correct), q_exp] + choice_cols
                csv_lines.append(",".join(row))
                
            csv_data = "\n".join(csv_lines)
            
            st.subheader("3. プレビュー & CSVダウンロード")
            
            # データフレーム表示
            df_preview = pd.DataFrame(questions)
            st.dataframe(df_preview, use_container_width=True)
            
            st.download_button(
                label="📥 ロイロノート用CSVファイルをダウンロード (.csv)",
                data=csv_data.encode("utf-8"),
                file_name="loylo_test.csv",
                mime="text/csv",
                type="primary"
            )
            
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
