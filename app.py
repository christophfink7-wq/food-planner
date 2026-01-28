import streamlit as st
import json
from datetime import datetime, timedelta
from google import genai
from streamlit_sortables import sort_items
import os
# --- 1. GOOGLE GENAI CLIENT SETUP ---
# This tells the app to look for the key in the cloud's secure vault
client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])

def load_recipes():
    try:
        with open("recipes.json", "r") as f:
            return json.load(f)
    except:
        return []

# --- 2. SESSION STATE ---
if 'num_days' not in st.session_state:
    st.session_state.num_days = 3
if 'meal_plan' not in st.session_state:
    st.session_state.meal_plan = []
if 'work_days' not in st.session_state:
    st.session_state.work_days = {}

# --- 3. UI: CLEANER BUTTONS ---
st.set_page_config(page_title="AI Chef", layout="centered") # 'Centered' makes the list look better on mobile
st.title("📅 Smart Plan Manager")

st.sidebar.header("Plan Duration")
# We use [1, 1] to make columns equal width
col_minus, col_plus = st.sidebar.columns([1, 1])

with col_minus:
    # use_container_width=True forces the button to fill the whole column
    if st.button("➖ Remove Day", use_container_width=True) and st.session_state.num_days > 1:
        st.session_state.num_days -= 1
        st.rerun()

with col_plus:
    if st.button("➕ Add Day", use_container_width=True) and st.session_state.num_days < 7:
        st.session_state.num_days += 1
        st.rerun()

st.sidebar.write(f"**Current Plan: {st.session_state.num_days} Days**")

# Get dates
day_labels = []
for i in range(st.session_state.num_days):
    d = datetime.now() + timedelta(days=i)
    label = d.strftime("%A (%d.%m)")
    day_labels.append(label)
    st.session_state.work_days[label] = st.sidebar.checkbox(f"Work Day: {label}", key=f"work_{label}")

# --- 4. SMART AI GENERATION ---
if st.button("🚀 Generate Plan", use_container_width=True):
    my_recipes = load_recipes()
    
    prompt = f"""
    You are a chef. Look at these recipes: {json.dumps(my_recipes)}
    Create a plan for {st.session_state.num_days} days.
    Constraints:
    1. No same main ingredient twice in a row.
    2. If a day is a 'Work Day', use 'is_work_friendly': 'Yes'.
    3. Days: {day_labels}
    
    Return ONLY a JSON list of recipe names. Example: ["Pasta", "Salad"]
    """
    
    with st.spinner("AI is thinking..."):
        try:
            response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
            clean_text = response.text.strip().replace("```json", "").replace("```", "")
            planned_names = json.loads(clean_text)
            
            st.session_state.meal_plan = []
            for name in planned_names:
                recipe = next((r for r in my_recipes if r['name'] == name), None)
                if recipe:
                    st.session_state.meal_plan.append(recipe)
        except:
            st.error("AI Error. Try again.")

# --- 5. VERTICAL DRAG AND DROP ---
if st.session_state.meal_plan:
    st.markdown("### 🖐️ Drag to Reorder")
    
    # We create a simple list of names for the sortable widget
    meal_names = [m['name'] for m in st.session_state.meal_plan]
    
    # This creates the vertical list
    sorted_names = sort_items(meal_names)

    # Re-sync the objects with the new order
    if sorted_names != meal_names:
        new_ordered_plan = []
        for name in sorted_names:
            recipe = next(r for r in st.session_state.meal_plan if r['name'] == name)
            new_ordered_plan.append(recipe)
        st.session_state.meal_plan = new_ordered_plan
        st.rerun()

    st.markdown("---")
    st.subheader("Final Schedule")
    for i, recipe in enumerate(st.session_state.meal_plan):
        # Safety check: if we dragged more items than days, stop
        if i >= len(day_labels): break
        
        day_text = day_labels[i]
        icon = "💼" if st.session_state.work_days.get(day_text) else "🏠"
        
        # Simple Card View
        st.info(f"**{day_text}** {icon} : {recipe['name']}")