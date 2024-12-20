"""
Scrapes and returns a csv file with airline price data
Returns:
    pd.Dataframe: Airfare price data between src and dest
"""
import re
import datetime
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup

class PriceScraper():
    """
    Scraper class that scrapes google flights
    """

    def __init__(self, src: str, dest: str, max_price: int, dates: list[str]) -> None:
        """
        Initialize PriceScraper
        Args:
            src (str): Source airport code
            dest (str): Destination airport code
            price (int): Maximum price
            dates (list[str]): List of departure dates to check
        """
        self.src = src
        self.dest = dest
        self.max_price = max_price
        self.dates = dates

    def get_pages(self, sleep_time: float = 0.5):
        """
        Load dynamic chrome browser and return page sources for all dates
        Args:
            sleep_time (float): Number of seconds to sleep between actions (default: 0.5)
        Returns:
            dict: Dictionary mapping dates to their page sources
        """
        self.preprocess()
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument('--window-size=1920,1200')
        driver = webdriver.Chrome(options=options)
        page_sources = {}
        
        try:
            # Navigate to Google Flights
            url = f'https://www.google.com/travel/flights/non-stop-flights-from-{self.src}-to-{self.dest}.html'
            driver.get(url)
            driver.implicitly_wait(10)
            
            # Accept cookies (only needed once)
            cookie_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//*[text()='Accept all']"))
            )
            cookie_button.click()
            time.sleep(sleep_time)
            
            # Click trip type dropdown (only needed once)
            trip_type_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@class="RLVa8 GeHXyb"]'))
            )
            trip_type_button.click()
            time.sleep(sleep_time)
            
            # Wait for dropdown and click "One way" (only needed once)
            one_way_option = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//li[contains(@class, 'VfPpkd-rymPhb-ibnC6b')]//span[text()='One way']"))
            )
            driver.execute_script("arguments[0].click();", one_way_option)
            time.sleep(sleep_time)



            # Loop through each date
            for i, date in enumerate(self.dates):
                try:
                    # Find and fill in the date
                    date_box = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Departure']"))
                    )
                    driver.execute_script("arguments[0].value='';", date_box)
                    date_box.send_keys(date)
                    date_box.send_keys(Keys.RETURN)
                    time.sleep(sleep_time)

                    if i > 0:
                        # sleep again for results to load
                        time.sleep(sleep_time)
                    elif i == 0:
                        # Click search button (only needed once)
                        search_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Search']"))
                        )
                        search_button.click()
                        time.sleep(sleep_time * 2)  # Extra time for results to load
                        # Initial setup for nonstop flights (only needed once)
                        stops_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, "//button[contains(@aria-label, 'Stops')]"))
                        )
                        stops_button.click()
                        time.sleep(sleep_time)

                        nonstop_option = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'Nonstop only')]"))
                        )
                        driver.execute_script("arguments[0].click();", nonstop_option)
                        time.sleep(sleep_time)

                        # Send ESC key
                        webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                        time.sleep(sleep_time)

                    # Store the page source for this date
                    page_sources[date] = driver.page_source

                except Exception as e:
                    print(f"Error processing date {date}: {str(e)}")
                    raise
                    # continue

        except Exception as e:
            print(f"Error: {str(e)}")
            driver.save_screenshot("error.png")
            raise
        finally:
            driver.quit()

        return page_sources
    def soupify(self,page: str) -> BeautifulSoup:
        """
        Return page to scrape as a BeautifulSoup object
        Args:
            page (str): Source page
        Returns:
            BeautifulSoup: parsed bs4 object
        """
        soup = BeautifulSoup(page, features="html.parser")
        return soup
    def parser(self, soup: BeautifulSoup, current_date: str) -> "list[dict]":
        """
        Helper parser function that scrapes required details

        Args:
            soup (BeautifulSoup): Soup object to scrape
            current_date (str): The date being processed

        Returns:
            list[dict]: list of dictionaries which store scraped flight information records
        """
        flights = soup.find_all(class_='pIav2d')
        data = []

        for flight in flights:
            dep_time = flight.find(class_='wtdjmc YMlIz ogfYpf tPgKwe').text
            dep_city = flight.find(class_='G2WY5c sSHqwe ogfYpf tPgKwe').text
            arr_time = flight.find(class_='XWcVob YMlIz ogfYpf tPgKwe').text
            arr_city = flight.find(class_='c8rWCd sSHqwe ogfYpf tPgKwe').text
            price_text = flight.find(class_=re.compile('YMlIz FpEdX')).text
            currency, price = price_text.split('\xa0')
            price = int(price)
            if price > self.max_price:
                continue
            airline = flight.find(class_='h1fkLb').span.text
            timestamp = datetime.datetime.now()
            info = {
                "Source": dep_city,
                "Departure Time": dep_time,
                "Destination": arr_city,
                "Arrival Time": arr_time,
                "Date": current_date,
                "Price": price,
                "Currency": currency,
                "Airline": airline,
                "Timestamp": timestamp
            }
            data.append(info)
        return data

    def create_df(self, data: "list[dict]") -> pd.DataFrame:
        """
        Helper function to convert data into a Pandas Dataframe

        Args:
            data (list[dict]): Flight Information data

        Returns:
            pd.DataFrame: data in the form of a pandas Dataframe
        """

        df = pd.DataFrame(data)
        return df
    def preprocess(self) -> None:
        """
        Helper Preprocessing function
        """
        self.src = self.src.replace(' ', '-')
        self.dest = self.dest.replace(' ', '-')
        