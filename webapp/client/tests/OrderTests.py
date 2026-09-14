import pytest
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

BASE_URL = "http://localhost:5173/" 

class TestOrder:
    def setup_method(self, method):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1280,720")
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.get(f"{BASE_URL}")
        self.driver.execute_script("window.localStorage.clear();")
        self.driver.execute_script("window.sessionStorage.clear();")
        self.driver.refresh()

    def teardown_method(self, method):
        time.sleep(1)
        self.driver.quit()

    #Stage 1: Testing expired card

    def test_expiredCard_ShouldShowValidationError(self):
        driver = self.driver
        wait = WebDriverWait(driver, 10)

        driver.get(f"{BASE_URL}login")

        wait.until(EC.element_to_be_clickable((By.ID, "email"))).send_keys("admin@store.com")
        wait.until(EC.element_to_be_clickable((By.ID, "password"))).send_keys("p@ssword1234")
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".w-100"))).click()

        wait.until(EC.url_contains("/dashboard"))

        driver.get(f"{BASE_URL}shop")

        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".product-card__image"))).click()

        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Add to bag')]"))).click()
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".drawer__body")))

        wait.until(EC.element_to_be_clickable((By.ID, "card-number"))).send_keys("4000 0000 0000 0069")
        wait.until(EC.element_to_be_clickable((By.ID, "card-expiry"))).send_keys("12/30")
        wait.until(EC.element_to_be_clickable((By.ID, "card-cvc"))).send_keys("123")
        wait.until(EC.element_to_be_clickable((By.ID, "card-name"))).send_keys("Admin")

        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".d-grid > .btn-primary"))).click()


        time.sleep(2)
        assert "/order/success/" not in driver.current_url, \
        f"Should NOT redirect to success page, got: {driver.current_url}"

        error_toast = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".alert-danger")))
        assert "Your card has expired" in error_toast.text, \
        f"Expected 'Your card has expired', got: {error_toast.text}"

   
   #Stage 2: Testing declined card
    def test_declinedCard_ShouldShowValidationError(self):
        driver = self.driver
        wait = WebDriverWait(driver, 10)

        driver.get(f"{BASE_URL}login")

        wait.until(EC.element_to_be_clickable((By.ID, "email"))).send_keys("admin@store.com")
        wait.until(EC.element_to_be_clickable((By.ID, "password"))).send_keys("p@ssword1234")
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".w-100"))).click()

        wait.until(EC.url_contains("/dashboard"))

        driver.get(f"{BASE_URL}shop")

        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".product-card__image"))).click()

        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Add to bag')]"))).click()
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".drawer__body")))

        wait.until(EC.element_to_be_clickable((By.ID, "card-number"))).send_keys("4000 0000 0000 0002")
        wait.until(EC.element_to_be_clickable((By.ID, "card-expiry"))).send_keys("12/30")
        wait.until(EC.element_to_be_clickable((By.ID, "card-cvc"))).send_keys("123")
        wait.until(EC.element_to_be_clickable((By.ID, "card-name"))).send_keys("Admin")

        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".d-grid > .btn-primary"))).click()


        time.sleep(2)
        assert "/order/success/" not in driver.current_url, \
        f"Should NOT redirect to success page, got: {driver.current_url}"

        error_toast = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".alert-danger")))
        assert "Your card was declined" in error_toast.text, \
        f"Expected 'Your card was declined', got: {error_toast.text}"
   
   #Stage 3: Testing insufficient funds cards
   
    def test_insufficientFundsCard_ShouldShowValidationError(self):
        driver = self.driver
        wait = WebDriverWait(driver, 10)

        driver.get(f"{BASE_URL}login")

        wait.until(EC.element_to_be_clickable((By.ID, "email"))).send_keys("admin@store.com")
        wait.until(EC.element_to_be_clickable((By.ID, "password"))).send_keys("p@ssword1234")
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".w-100"))).click()

        wait.until(EC.url_contains("/dashboard"))

        driver.get(f"{BASE_URL}shop")

        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".product-card__image"))).click()

        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Add to bag')]"))).click()
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".drawer__body")))

        wait.until(EC.element_to_be_clickable((By.ID, "card-number"))).send_keys("4000 0000 0000 9995")
        wait.until(EC.element_to_be_clickable((By.ID, "card-expiry"))).send_keys("12/30")
        wait.until(EC.element_to_be_clickable((By.ID, "card-cvc"))).send_keys("123")
        wait.until(EC.element_to_be_clickable((By.ID, "card-name"))).send_keys("Admin")

        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".d-grid > .btn-primary"))).click()


        time.sleep(2)
        assert "/order/success/" not in driver.current_url, \
        f"Should NOT redirect to success page, got: {driver.current_url}"

        error_toast = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".alert-danger")))
        assert "Your card has insufficient funds" in error_toast.text, \
        f"Expected 'Your card has insufficient funds', got: {error_toast.text}"
   
   
   #Stage 4: Testing incorrect security code card
    def test_incorrectSecurityCodeCard_ShouldShowValidationError(self):
        driver = self.driver
        wait = WebDriverWait(driver, 10)

        driver.get(f"{BASE_URL}login")

        wait.until(EC.element_to_be_clickable((By.ID, "email"))).send_keys("admin@store.com")
        wait.until(EC.element_to_be_clickable((By.ID, "password"))).send_keys("p@ssword1234")
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".w-100"))).click()

        wait.until(EC.url_contains("/dashboard"))

        driver.get(f"{BASE_URL}shop")

        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".product-card__image"))).click()

        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Add to bag')]"))).click()
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".drawer__body")))

        wait.until(EC.element_to_be_clickable((By.ID, "card-number"))).send_keys("4000 0000 0000 0127")
        wait.until(EC.element_to_be_clickable((By.ID, "card-expiry"))).send_keys("12/30")
        wait.until(EC.element_to_be_clickable((By.ID, "card-cvc"))).send_keys("123")
        wait.until(EC.element_to_be_clickable((By.ID, "card-name"))).send_keys("Admin")

        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".d-grid > .btn-primary"))).click()


        time.sleep(2)
        assert "/order/success/" not in driver.current_url, \
        f"Should NOT redirect to success page, got: {driver.current_url}"

        error_toast = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".alert-danger")))
        assert "The security code for your card is incorrect" in error_toast.text, \
        f"Expected 'The security code for your card is incorrect', got: {error_toast.text}"
   
   
   #Stage 5: Testing processing error card
   
    def test_processingErrorCard_ShouldShowValidationError(self):
        driver = self.driver
        wait = WebDriverWait(driver, 10)

        driver.get(f"{BASE_URL}login")

        wait.until(EC.element_to_be_clickable((By.ID, "email"))).send_keys("admin@store.com")
        wait.until(EC.element_to_be_clickable((By.ID, "password"))).send_keys("p@ssword1234")
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".w-100"))).click()

        wait.until(EC.url_contains("/dashboard"))

        driver.get(f"{BASE_URL}shop")

        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".product-card__image"))).click()

        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Add to bag')]"))).click()
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".drawer__body")))

        wait.until(EC.element_to_be_clickable((By.ID, "card-number"))).send_keys("4000 0000 0000 0119")
        wait.until(EC.element_to_be_clickable((By.ID, "card-expiry"))).send_keys("12/30")
        wait.until(EC.element_to_be_clickable((By.ID, "card-cvc"))).send_keys("123")
        wait.until(EC.element_to_be_clickable((By.ID, "card-name"))).send_keys("Admin")

        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".d-grid > .btn-primary"))).click()


        time.sleep(2)
        assert "/order/success/" not in driver.current_url, \
        f"Should NOT redirect to success page, got: {driver.current_url}"

        error_toast = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".alert-danger")))
        assert "An error occurred while processing your card" in error_toast.text, \
        f"Expected 'An error occurred while processing your card', got: {error_toast.text}"
   
    #Stage ... : Testing checkout success of mastercard

    def test_checkout_approved_mastercard(self):
        driver = self.driver
        wait = WebDriverWait(driver, 10)

        driver.get(f"{BASE_URL}login")

        wait.until(EC.element_to_be_clickable((By.ID, "email"))).send_keys("admin@store.com")
        wait.until(EC.element_to_be_clickable((By.ID, "password"))).send_keys("p@ssword1234")
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".w-100"))).click()

        wait.until(EC.url_contains("/dashboard"))

        driver.get(f"{BASE_URL}shop")

        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".product-card__image"))).click()

        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Add to bag')]"))).click()
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".drawer__body")))

        wait.until(EC.element_to_be_clickable((By.ID, "card-number"))).send_keys("5555 5555 5555 4444")
        wait.until(EC.element_to_be_clickable((By.ID, "card-expiry"))).send_keys("12/30")
        wait.until(EC.element_to_be_clickable((By.ID, "card-cvc"))).send_keys("123")
        wait.until(EC.element_to_be_clickable((By.ID, "card-name"))).send_keys("Admin")

        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".d-grid > .btn-primary"))).click()

        wait.until(EC.url_contains("/order/success/"))

        wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "View order"))).click()

        wait.until(EC.url_contains("/order/"))
        wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, "h1.page-title"), "Order #"))
        wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".text-capitalize"), "Mastercard"))
        

        card_info = driver.find_element(By.CSS_SELECTOR, ".text-capitalize")
        assert "Mastercard" in card_info.text and "4444" in card_info.text
        
        #Stage ... : Testing checkout success of visa
        
    def test_checkout_approved_visa(self):
        driver = self.driver
        wait = WebDriverWait(driver, 10)

        driver.get(f"{BASE_URL}login")

        wait.until(EC.element_to_be_clickable((By.ID, "email"))).send_keys("admin@store.com")
        wait.until(EC.element_to_be_clickable((By.ID, "password"))).send_keys("p@ssword1234")
        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".w-100"))).click()

        wait.until(EC.url_contains("/dashboard"))

        driver.get(f"{BASE_URL}shop")

        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".product-card__image"))).click()

        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Add to bag')]"))).click()
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".drawer__body")))

        wait.until(EC.element_to_be_clickable((By.ID, "card-number"))).send_keys("4242 4242 4242 4242")
        wait.until(EC.element_to_be_clickable((By.ID, "card-expiry"))).send_keys("12/30")
        wait.until(EC.element_to_be_clickable((By.ID, "card-cvc"))).send_keys("123")
        wait.until(EC.element_to_be_clickable((By.ID, "card-name"))).send_keys("Admin")

        wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".d-grid > .btn-primary"))).click()

        wait.until(EC.url_contains("/order/success/"))

        wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "View order"))).click()

        wait.until(EC.url_contains("/order/"))
        wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, "h1.page-title"), "Order #"))
        wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".text-capitalize"), "Visa"))
        

        card_info = driver.find_element(By.CSS_SELECTOR, ".text-capitalize")
        assert "Visa" in card_info.text and "4242" in card_info.text
