import streamlit as st
import json
import time
from datetime import datetime, timedelta
from google import genai
from streamlit_sortables import sort_items
import os

# --- 1. SETUP & CONFIGURATION ---
st.set_page_config(
    page_title="AI Meal Planner",
    page_icon="🥑",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Handle API Key (Local vs Cloud)
try:
    # Try getting key from Cloud Secrets first
    api_key = st.secrets["GOOGLE_API_KEY"]
except:
    # Fallback for local testing (Replace with your actual key if testing locally)
    api_key = "YOUR_API_KEY_HERE"

client = genai.Client(api_key=api_key)

def load_recipes():
    try:
        with open("recipes.json", "r") as f:
            return json.load(f)
    except:
        return []

# --- 2. SESSION STATE MANAGEMENT ---
if 'num_days' not in st.session_state:
    st.session_state.num_days = 3
if 'meal_plan' not in st.session_state:
    st.session_state.meal_plan = []
if 'work_days' not in st.session_state:
    st.session_state.work_days = {}

# --- 3. MODERN SIDEBAR UI ---
with st.sidebar:
    st.header("⚙️ Planner Settings")
    
    st.markdown("### 📅 Duration")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➖ Less", use_container_width=True) and st.session_state.num_days > 1:
            st.session_state.num_days -= 1
            st.rerun()
    with col2:
        if st.button("➕ More", use_container_width=True) and st.session_state.num_days < 7:
            st.session_state.num_days += 1
            st.rerun()
    
    st.info(f"Planning for: **{st.session_state.num_days} Days**")
    
    st.markdown("### 💼 Schedule")
    st.caption("Check days you are at work:")
    
    # Generate dates dynamically
    day_labels = []
    for i in range(st.session_state.num_days):
        d = datetime.now() + timedelta(days=i)
        label = d.strftime("%A")
        full_date = d.strftime("%d.%m")
        day_labels.append(f"{label} ({full_date})")
        
        # Styled Checkbox
        st.session_state.work_days[day_labels[i]] = st.checkbox(
            f"{label}", 
            key=f"work_{i}",
            help="Filters for portable meals"
        )

# --- 4. MAIN INTERFACE ---
st.title("🥑 Smart Meal Planner")
st.markdown("Drag meals to reorder, or swap instantly with *Jause*.")

# AI Generation Block
if st.button("✨ Generate AI Plan", type="primary", use_container_width=True):
    my_recipes = load_recipes()
    
    # Using st.status for better UX feedback
    with st.status("👨‍🍳 AI Chef is working...", expanded=True) as status:
        st.write("Reading your cookbook...")
        time.sleep(0.5)
        st.write("Checking ingredients for variety...")
        
        prompt = f"""
        You are a chef. Look at these recipes: {json.dumps(my_recipes)}
        Create a plan for {st.session_state.num_days} days.
        Constraints:
        1. No same main ingredient twice in a row.
        2. If a day is a 'Work Day', use 'is_work_friendly': 'Yes'.
        3. Days: {day_labels}
        
        Return ONLY a JSON list of recipe names. Example: ["Pasta", "Salad"]
        """
        
        try:
            response = client.models.generate_content(model="gemini-3-flash-preview", contents=prompt)
            clean_text = response.text.strip().replace("```json", "").replace("```", "")
            planned_names = json.loads(clean_text)
            
            # Reconstruct the recipe objects
            st.session_state.meal_plan = []
            for name in planned_names:
                recipe = next((r for r in my_recipes if r['name'] == name), None)
                if recipe:
                    st.session_state.meal_plan.append(recipe)
            
            status.update(label="✅ Plan Ready!", state="complete", expanded=False)
        except:
            status.update(label="❌ Error", state="error")
            st.error("AI could not generate the plan. Please try again.")

# --- 5. DRAG & DROP & CARDS ---
if st.session_state.meal_plan:
    st.divider()
    
    # 1. The Drag-and-Drop List (Names Only)
    with st.expander("🖐️  **Drag to Reorder Meals**", expanded=True):
        meal_names = [m['name'] for m in st.session_state.meal_plan]
        sorted_names = sort_items(meal_names)

        if sorted_names != meal_names:
            new_ordered_plan = []
            for name in sorted_names:
                # Find recipe (handle duplicates or Jause items)
                recipe = next((r for r in st.session_state.meal_plan if r['name'] == name), None)
                # If it's a new Jause not in original list, create it
                if not recipe and name == "🥪 Jause (Cold Snack)":
                    recipe = {"name": "🥪 Jause (Cold Snack)", "category": "Snack", "is_work_friendly": "Yes"}
                if recipe:
                    new_ordered_plan.append(recipe)
            st.session_state.meal_plan = new_ordered_plan
            st.rerun()

    st.subheader("Your Final Schedule")

    # 2. The Final Visual Cards
    for i, recipe in enumerate(st.session_state.meal_plan):
        # Stop loop if days were reduced but plan is still long
        if i >= len(day_labels): break
        
        day_text = day_labels[i]
        is_work_day = st.session_state.work_days.get(day_text, False)
        
        # --- CARD DESIGN ---
        # Container with border creates a "Card" look
        with st.container(border=True):
            col_date, col_meal, col_action = st.columns([1.5, 3, 1.2])
            
            with col_date:
                st.markdown(f"**{day_text}**")
                if is_work_day:
                    st.caption("💼 Office")
                else:
                    st.caption("🏠 Home")
            
            with col_meal:
                st.markdown(f"#### {recipe['name']}")
                # Show tags if they exist
                tags = f"🏷️ {recipe.get('category', 'General')}"
                if recipe.get('is_work_friendly') == 'Yes':
                    tags += " • 🥡 Portable"
                st.caption(tags)

            with col_action:
                # The JAUSE Button
                # If it's already Jause, show a disabled button or text
                if "Jause" in recipe['name']:
                    st.button("✅ Set", key=f"done_{i}", disabled=True)
                else:
                    if st.button("🥨 Jause", key=f"jause_{i}", help="Swap this meal for a cold snack"):
                        # Update the state to Jause
                        st.session_state.meal_plan[i] = {
                            "name": "🥪 Jause (Cold Snack)",
                            "category": "Snack",
                            "is_work_friendly": "Yes"
                        }
                        st.rerun()
                        
