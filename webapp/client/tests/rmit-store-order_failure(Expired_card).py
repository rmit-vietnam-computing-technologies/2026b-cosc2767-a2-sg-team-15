import pytest
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class TestCheckoutExpired:

  def setup_method(self, method):
    self.driver = webdriver.Edge()
    self.driver.get("http://localhost:4173/")
    self.driver.execute_script("window.localStorage.clear();")
    self.driver.execute_script("window.sessionStorage.clear();")
    self.driver.refresh()

  def teardown_method(self, method):
    self.driver.quit()

