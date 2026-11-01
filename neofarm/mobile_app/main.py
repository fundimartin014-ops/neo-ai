from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label

from neofarm.multi_farm import switch_farm, list_farms
from neofarm.dashboard import generate_dashboard
from neofarm.self_learning import optimize_feed
from neofarm.autonomous import run_daily_once

class NeoFarmUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", **kwargs)

        self.label = Label(text="NeoFarm AI Ready", size_hint_y=0.6)
        self.add_widget(self.label)

        self.add_widget(Button(text="Switch to Alpha Farm",
                               on_press=lambda x: self.switch("Alpha")))

        self.add_widget(Button(text="Show Dashboard",
                               on_press=lambda x: self.show_dashboard()))

        self.add_widget(Button(text="Optimize Feed",
                               on_press=lambda x: self.optimize()))

        self.add_widget(Button(text="Run Daily Autonomy",
                               on_press=lambda x: self.autonomy()))

    def switch(self, farm):
        switch_farm(farm)
        self.label.text = f"Switched to {farm}"

    def show_dashboard(self):
        self.label.text = generate_dashboard()

    def optimize(self):
        data = optimize_feed()
        self.label.text = f"Feed optimized for {len(data)} cows"

    def autonomy(self):
        run_daily_once()
        self.label.text = "Daily autonomy executed"

class NeoFarmApp(App):
    def build(self):
        return NeoFarmUI()

if __name__ == "__main__":
    NeoFarmApp().run()
