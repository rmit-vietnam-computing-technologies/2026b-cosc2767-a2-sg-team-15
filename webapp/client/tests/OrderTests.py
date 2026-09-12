import pytest
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "http://localhost:4173/" 

class TestOrder:
    def setup_method(self, method):
        self.driver = webdriver.Edge()
        self.driver.get(f"{BASE_URL}")
        self.driver.execute_script("window.localStorage.clear();")
        self.driver.execute_script("window.sessionStorage.clear();")
        self.driver.refresh()

    def teardown_method(self, method):
        self.driver.quit()

    def test_expiredCard_ShouldShowValidationError(self):
        driver = self.driver
        wait = WebDriverWait(driver, 10)

        driver.get(f"{BASE_URL}login")

        wait.until(EC.element_to_be_clickable((By.ID, "email"))).send_keys("admin@rmit.edu.au")
        wait.until(EC.element_to_be_clickable((By.ID, "password"))).send_keys("'RmitStore2767!'")
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


    def test_checkout_approved_mastercard_visa(self):
        driver = self.driver
        wait = WebDriverWait(driver, 10)

        driver.get(f"{BASE_URL}login")

        wait.until(EC.element_to_be_clickable((By.ID, "email"))).send_keys("admin@rmit.edu.au")
        wait.until(EC.element_to_be_clickable((By.ID, "password"))).send_keys("'RmitStore2767!'")
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

        assert "/order/success/" in driver.current_url

        wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "View order"))).click()

        wait.until(EC.url_contains("/order/"))

        order_heading = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.page-title")))
        assert "Order #" in order_heading.text

        card_info = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".text-capitalize")))
        assert "Mastercard" in card_info.text and "4444" in card_info.text
        
    def test_checkout_approved(self):
        driver = self.driver
        wait = WebDriverWait(driver, 10)

        driver.get(f"{BASE_URL}login")

        wait.until(EC.element_to_be_clickable((By.ID, "email"))).send_keys("admin@rmit.edu.au")
        wait.until(EC.element_to_be_clickable((By.ID, "password"))).send_keys("'RmitStore2767!'")
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

        assert "/order/success/" in driver.current_url

        wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "View order"))).click()

        wait.until(EC.url_contains("/order/"))

        order_heading = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.page-title")))
        assert "Order #" in order_heading.text

        card_info = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".text-capitalize")))
        assert "Visa" in card_info.text and "4242" in card_info.text