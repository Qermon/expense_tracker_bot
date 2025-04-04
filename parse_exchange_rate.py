from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def usd_exchange_rate():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                         'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 '
                         'Safari/537.36 OPR/77.0.4054.172')
    driver = webdriver.Chrome(options=options)

    try:
        url = 'https://minfin.com.ua/ua/currency/usd/'
        driver.get(url)

        usd_rate_element = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'sc-1x32wa2-9'))
        )

        usd_rate = usd_rate_element.text.split('\n')[0]
        usd_rate_float = float(usd_rate.replace(',', '.'))

        # print(f"Отримано курс долара: {usd_rate_float}")
        return usd_rate_float

    except Exception as ex:
        print(f"Курс не знайдено: {ex}")
        return None

    finally:
        driver.quit()


if __name__ == "__main__":
    usd_exchange_rate()
