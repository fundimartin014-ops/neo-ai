from neofarm.milk import milk_records
from neofarm.milk_forecast import forecast_milk
from neofarm.disease_predict import predict_disease
from neofarm.multi_farm import get_current_farm, load_farm_data, save_farm_data

def learn_feed_ratios(farm_name=None):
    if not farm_name:
        farm_name = get_current_farm()
    
    milk_data = load_farm_data(farm_name, "milk.json")
    feed_ratios = {}
    
    for cow, records in milk_data.items():
        if len(records) < 3:
            continue
        avg_milk = sum(records)/len(records)
        # simple learning: adjust feed ratio per cow
        feed_ratios[cow] = round(avg_milk * 1.05, 1)  # +5% optimization
    save_farm_data(farm_name, "feed_ratios.json", feed_ratios)
    return feed_ratios


def optimize_feed(farm_name=None):
    return learn_feed_ratios(farm_name)


def self_optimize(farm_name=None):
    return optimize_feed(farm_name)
