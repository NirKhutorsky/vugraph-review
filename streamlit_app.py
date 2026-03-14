"""VuGraph Candidate Review UI — standalone Streamlit app.

Reads candidates from data/all_candidates.json.
Review state persists in session (export accepted before closing).
Password-protected via st.secrets["app_password"].
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

DATA_DIR = Path(__file__).parent / "data"
BUNDLE_FILE = DATA_DIR / "all_candidates.json"

SUIT_SYMBOLS = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}
SUIT_COLORS = {"S": "#000000", "H": "#FF0000", "D": "#FF8C00", "C": "#008000"}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def check_password() -> bool:
    """Simple password gate."""
    try:
        correct_password = st.secrets["app_password"]
    except (KeyError, AttributeError):
        st.error("app_password not configured in secrets.")
        return False

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    password = st.text_input("Enter password to access the review UI:", type="password")
    if password:
        if password == correct_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@st.cache_data
def load_candidates() -> list[dict]:
    """Load candidates from bundled JSON."""
    if not BUNDLE_FILE.exists():
        return []
    try:
        return json.loads(BUNDLE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return []


def get_review_state() -> dict:
    """Get review state from session."""
    if "review_state" not in st.session_state:
        st.session_state.review_state = {}
    return st.session_state.review_state


def save_review(review_state: dict, candidate_id: str, status: str, notes: str) -> None:
    """Save a review decision to session state."""
    review_state[candidate_id] = {
        "status": status,
        "notes": notes,
        "timestamp": datetime.now().isoformat(),
    }
    st.session_state.review_state = review_state


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def format_hand(pbn: str) -> str:
    """Format a PBN hand string with colored suit symbols."""
    suits_order = ["S", "H", "D", "C"]
    parts = pbn.split(".")
    if len(parts) != 4:
        return pbn

    formatted = []
    for suit, cards in zip(suits_order, parts):
        symbol = SUIT_SYMBOLS[suit]
        color = SUIT_COLORS[suit]
        cards_display = cards if cards else "—"
        formatted.append(
            f'<span style="color:{color};font-weight:bold">{symbol}</span> {cards_display}'
        )
    return "&nbsp;&nbsp;".join(formatted)


def render_score_badge(score: int) -> str:
    """Return an HTML score badge with color coding."""
    if score >= 70:
        color = "#22C55E"
    elif score >= 50:
        color = "#F59E0B"
    elif score >= 30:
        color = "#F97316"
    else:
        color = "#EF4444"

    return (
        f'<span style="background:{color};color:white;padding:2px 8px;'
        f'border-radius:12px;font-weight:bold;font-size:0.9em">'
        f'{score}</span>'
    )


def render_hand_diagram(hands: dict) -> None:
    """Render a compass-style hand diagram."""
    st.markdown("#### Hand Diagram")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"**North**<br>{format_hand(hands.get('N', ''))}", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([2, 0.5, 2])
    with col1:
        st.markdown(f"**West**<br>{format_hand(hands.get('W', ''))}", unsafe_allow_html=True)
    with col3:
        st.markdown(f"**East**<br>{format_hand(hands.get('E', ''))}", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            f"**South (Player)** 🎯<br>{format_hand(hands.get('S', ''))}",
            unsafe_allow_html=True,
        )


def render_auction_table(auction: list[str], dealer: str) -> None:
    """Render auction as a 4-column table starting from dealer."""
    seats = ["W", "N", "E", "S"]
    dealer_idx = seats.index(dealer) if dealer in seats else 0

    rows: list[list[str]] = []
    current_row = [""] * 4
    col = dealer_idx

    for bid in auction:
        current_row[col] = bid
        col += 1
        if col >= 4:
            rows.append(current_row)
            current_row = [""] * 4
            col = 0

    if any(c for c in current_row):
        rows.append(current_row)

    header = "| W | N | E | S |\n|---|---|---|---|"
    body = "\n".join(
        f"| {r[0] or ''} | {r[1] or ''} | {r[2] or ''} | {r[3] or ''} |"
        for r in rows
    )
    st.markdown(f"{header}\n{body}")


def render_score_breakdown(candidate: dict) -> None:
    """Render score breakdown in an expander."""
    breakdown = candidate.get("score_breakdown", {})
    if not breakdown:
        return

    with st.expander("Score Breakdown"):
        for factor, value in breakdown.items():
            bar_pct = int(value * 100)
            st.markdown(
                f"**{factor.capitalize()}**: {value:.2f} "
                f'<div style="background:#334155;border-radius:4px;height:8px;width:200px;display:inline-block">'
                f'<div style="background:#3B82F6;border-radius:4px;height:8px;width:{bar_pct * 2}px"></div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def render_lead_candidate(candidate: dict, review_state: dict) -> None:
    """Render a lead candidate card."""
    cid = candidate["id"]
    score = candidate.get("quality_score", 0)

    st.markdown(
        f"### Lead Candidate: `{cid}` {render_score_badge(score)}",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**Contract:** {candidate.get('contract', '?')}")
        st.markdown(f"**Declarer:** {candidate.get('declarer', '?')}")
    with col2:
        st.markdown(f"**Dealer:** {candidate.get('dealer', '?')}")
        st.markdown(f"**Vulnerability:** {candidate.get('vulnerability', '?')}")
    with col3:
        st.markdown(f"**Non-pass bids:** {candidate.get('non_pass_bid_count', '?')}")
        src = candidate.get("source_vugraph_id", "?")
        brd = candidate.get("source_board_num", "?")
        st.markdown(f"**Source:** VG {src} Board {brd}")

    render_score_breakdown(candidate)

    with st.expander("Rotation Verification"):
        orig_d = candidate.get("original_declarer", "?")
        orig_l = candidate.get("original_leader", "?")
        orig_v = candidate.get("original_vulnerability", "?")
        rot_d = candidate.get("declarer", "?")
        rot_v = candidate.get("vulnerability", "?")
        st.markdown(
            f"**Original:** declarer={orig_d}, leader={orig_l}, vul={orig_v}  \n"
            f"**Rotated:** declarer={rot_d}, leader=S, vul={rot_v}"
        )

    render_hand_diagram(candidate.get("hands", {}))

    st.markdown("#### Auction")
    render_auction_table(
        candidate.get("bidding_sequence", []),
        candidate.get("dealer", "N"),
    )

    render_review_controls(cid, review_state)


def render_bidding_candidate(candidate: dict, review_state: dict) -> None:
    """Render a bidding candidate card."""
    cid = candidate["id"]
    score = candidate.get("quality_score", 0)

    st.markdown(
        f"### Bidding Candidate: `{cid}` {render_score_badge(score)}",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**Dealer:** {candidate.get('dealer', '?')}")
        st.markdown(f"**Vulnerability:** {candidate.get('vulnerability', '?')}")
    with col2:
        st.markdown(f"**Open room:** {candidate.get('open_room_contract', '?')}")
        st.markdown(f"**Closed room:** {candidate.get('closed_room_contract', '?')}")
    with col3:
        st.markdown(f"**Divergence point:** {candidate.get('divergence_point', '?')}")
        st.markdown(f"**Differing calls:** {candidate.get('differing_calls', '?')}")

    render_score_breakdown(candidate)

    render_hand_diagram(candidate.get("hands", {}))

    st.markdown("#### Auctions (Open vs Closed)")
    col1, col2 = st.columns(2)
    dealer = candidate.get("dealer", "N")
    with col1:
        st.markdown("**Open Room**")
        render_auction_table(candidate.get("open_room_auction", []), dealer)
    with col2:
        st.markdown("**Closed Room**")
        render_auction_table(candidate.get("closed_room_auction", []), dealer)

    render_review_controls(cid, review_state)


def render_review_controls(cid: str, review_state: dict) -> None:
    """Render accept/reject/notes controls."""
    current = review_state.get(cid, {})
    current_status = current.get("status", "pending")
    current_notes = current.get("notes", "")

    st.divider()

    col1, col2, col3, col4 = st.columns([1, 1, 1, 3])

    with col1:
        if st.button("✅ Accept", key=f"accept_{cid}",
                      type="primary" if current_status != "accepted" else "secondary"):
            save_review(review_state, cid, "accepted", current_notes)
            st.rerun()

    with col2:
        if st.button("❌ Reject", key=f"reject_{cid}",
                      type="primary" if current_status != "rejected" else "secondary"):
            save_review(review_state, cid, "rejected", current_notes)
            st.rerun()

    with col3:
        if current_status != "pending":
            if st.button("↩️ Reset", key=f"reset_{cid}"):
                save_review(review_state, cid, "pending", current_notes)
                st.rerun()

    status_icons = {
        "accepted": "✅ Accepted",
        "rejected": "❌ Rejected",
        "pending": "⏳ Pending",
    }
    st.markdown(f"**Status:** {status_icons.get(current_status, current_status)}")

    notes = st.text_area("Notes", value=current_notes, key=f"notes_{cid}")
    if st.button("💾 Save Notes", key=f"save_notes_{cid}"):
        save_review(review_state, cid, review_state.get(cid, {}).get("status", "pending"), notes)
        st.success("Notes saved.")


def export_accepted(candidates: list[dict], review_state: dict) -> list[dict]:
    """Export accepted candidates."""
    return [c for c in candidates if review_state.get(c["id"], {}).get("status") == "accepted"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="VuGraph Candidate Review", layout="wide")
    st.title("VuGraph Scraper — Candidate Review")

    if not check_password():
        return

    all_candidates = load_candidates()
    review_state = get_review_state()

    if not all_candidates:
        st.warning("No candidates found. Ensure data/all_candidates.json exists.")
        return

    # Sidebar: filters
    with st.sidebar:
        st.header("Filters")

        sort_options = ["Quality Score (high→low)", "Quality Score (low→high)", "ID"]
        selected_sort = st.selectbox("Sort by", sort_options)

        candidate_types = sorted({c.get("candidate_type", "unknown") for c in all_candidates})
        selected_type = st.selectbox("Type", ["all"] + candidate_types)

        selected_status = st.selectbox("Review Status", ["all", "pending", "accepted", "rejected"])

        min_score, max_score = st.slider("Quality Score Range", 0, 100, (0, 100))

        tournaments = sorted({c.get("tournament") or "Unknown" for c in all_candidates})
        if len(tournaments) > 1:
            selected_tournament = st.selectbox("Tournament", ["all"] + tournaments)
        else:
            selected_tournament = "all"

        selected_vul = st.selectbox("Vulnerability", ["all", "None", "NS", "EW", "Both"])

    # Apply filters
    filtered = all_candidates
    if selected_type != "all":
        filtered = [c for c in filtered if c.get("candidate_type") == selected_type]
    if selected_status != "all":
        filtered = [
            c for c in filtered
            if review_state.get(c["id"], {}).get("status", "pending") == selected_status
        ]
    filtered = [
        c for c in filtered
        if min_score <= c.get("quality_score", 0) <= max_score
    ]
    if selected_tournament != "all":
        filtered = [c for c in filtered if (c.get("tournament") or "Unknown") == selected_tournament]
    if selected_vul != "all":
        filtered = [c for c in filtered if c.get("vulnerability") == selected_vul]

    # Apply sort
    if selected_sort == "Quality Score (high→low)":
        filtered.sort(key=lambda c: c.get("quality_score", 0), reverse=True)
    elif selected_sort == "Quality Score (low→high)":
        filtered.sort(key=lambda c: c.get("quality_score", 0))
    else:
        filtered.sort(key=lambda c: c.get("id", ""))

    # Sidebar: stats
    with st.sidebar:
        st.divider()
        st.header("Stats")
        total = len(all_candidates)
        accepted_count = sum(1 for c in all_candidates if review_state.get(c["id"], {}).get("status") == "accepted")
        rejected_count = sum(1 for c in all_candidates if review_state.get(c["id"], {}).get("status") == "rejected")
        pending_count = total - accepted_count - rejected_count

        st.metric("Total", total)
        col1, col2, col3 = st.columns(3)
        col1.metric("Accepted", accepted_count)
        col2.metric("Rejected", rejected_count)
        col3.metric("Pending", pending_count)

        scores = [c.get("quality_score", 0) for c in all_candidates]
        if scores:
            st.markdown(f"**Avg Score:** {sum(scores) / len(scores):.0f}")

        st.markdown(f"**Showing:** {len(filtered)} of {total}")
        st.caption("⚠️ Session persistence — export before closing!")

        st.divider()
        if st.button("📦 Export Accepted", type="primary"):
            accepted_data = export_accepted(all_candidates, review_state)
            if accepted_data:
                export_json = json.dumps(accepted_data, indent=2, ensure_ascii=False)
                st.download_button(
                    label=f"Download ({len(accepted_data)} candidates)",
                    data=export_json,
                    file_name="accepted_candidates.json",
                    mime="application/json",
                )
            else:
                st.info("No accepted candidates to export.")

    # Pagination
    if not filtered:
        st.info("No candidates match your filters.")
        return

    if "page_idx" not in st.session_state:
        st.session_state.page_idx = 0

    st.session_state.page_idx = max(0, min(st.session_state.page_idx, len(filtered) - 1))

    col1, col2, col3, col4 = st.columns([1, 1, 2, 2])
    with col1:
        if st.button("⬅️ Previous") and st.session_state.page_idx > 0:
            st.session_state.page_idx -= 1
            st.rerun()
    with col2:
        if st.button("➡️ Next") and st.session_state.page_idx < len(filtered) - 1:
            st.session_state.page_idx += 1
            st.rerun()
    with col3:
        st.markdown(f"**{st.session_state.page_idx + 1} of {len(filtered)}**")

    st.divider()

    candidate = filtered[st.session_state.page_idx]
    ctype = candidate.get("candidate_type", "unknown")

    if ctype == "lead":
        render_lead_candidate(candidate, review_state)
    elif ctype == "bidding":
        render_bidding_candidate(candidate, review_state)
    else:
        st.error(f"Unknown candidate type: {ctype}")
        st.json(candidate)


if __name__ == "__main__":
    main()
