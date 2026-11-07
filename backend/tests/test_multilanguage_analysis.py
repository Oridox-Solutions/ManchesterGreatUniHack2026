import pytest

from app.services.analysis import PullRequestAnalysisService
from app.services.github import GitHubChangedFile, GitHubPullRequest


CASES = [
    {
        "id": "kotlin",
        "production_path": "src/main/kotlin/demo/AuthService.kt",
        "production": '''package demo

class AuthService {
    fun login(email: String): Boolean {
        return email.isNotBlank()
    }

    fun logout(): Boolean {
        return true
    }
}
''',
        "test_path": "src/test/kotlin/demo/AuthServiceTest.kt",
        "tests": '''package demo

import org.junit.jupiter.api.Test

class AuthServiceTest {
    @Test
    fun loginRejectsBlankEmail() {
        service.login(" ")
    }

    @Test
    fun logoutClearsSession() {
        service.logout()
    }
}
''',
        "patch": '''@@ -3,5 +3,5 @@
 class AuthService {
     fun login(email: String): Boolean {
-        return email.isNotEmpty()
+        return email.isNotBlank()
     }
''',
        "selected": "loginRejectsBlankEmail",
        "framework": "junit",
    },
    {
        "id": "csharp",
        "production_path": "src/Demo/Services/AuthService.cs",
        "production": '''namespace Demo.Services;

public class AuthService
{
    public bool Login(string email)
    {
        return !string.IsNullOrWhiteSpace(email);
    }

    public bool Logout()
    {
        return true;
    }
}
''',
        "test_path": "tests/Demo.Tests/AuthServiceTests.cs",
        "tests": '''using Demo.Services;
using Xunit;

namespace Demo.Tests;

public class AuthServiceTests
{
    [Fact]
    public void LoginRejectsBlankEmail()
    {
        service.Login(" ");
    }

    [Fact]
    public void LogoutClearsSession()
    {
        service.Logout();
    }
}
''',
        "patch": '''@@ -4,7 +4,7 @@
 {
     public bool Login(string email)
     {
-        return email.Length > 0;
+        return !string.IsNullOrWhiteSpace(email);
     }
''',
        "selected": "LoginRejectsBlankEmail",
        "framework": "xunit",
    },
    {
        "id": "ruby",
        "production_path": "lib/auth_service.rb",
        "production": '''class AuthService
  def login(email)
    !email.strip.empty?
  end

  def logout
    true
  end
end
''',
        "test_path": "spec/auth_service_spec.rb",
        "tests": '''require_relative "../lib/auth_service"

RSpec.describe AuthService do
  it "rejects blank login" do
    expect(AuthService.new.login(" ")).to be(false)
  end

  it "clears session on logout" do
    expect(AuthService.new.logout).to be(true)
  end
end
''',
        "patch": '''@@ -1,5 +1,5 @@
 class AuthService
   def login(email)
-    !email.empty?
+    !email.strip.empty?
   end
''',
        "selected": "rejects blank login",
        "framework": "rspec",
    },
    {
        "id": "php",
        "production_path": "src/Services/AuthService.php",
        "production": '''<?php

namespace App\\Services;

class AuthService
{
    public function login(string $email): bool
    {
        return trim($email) !== "";
    }

    public function logout(): bool
    {
        return true;
    }
}
''',
        "test_path": "tests/AuthServiceTest.php",
        "tests": '''<?php

namespace Tests;

use App\\Services\\AuthService;

class AuthServiceTest
{
    public function testLoginRejectsBlankEmail(): void
    {
        $service->login(" ");
    }

    public function testLogoutClearsSession(): void
    {
        $service->logout();
    }
}
''',
        "patch": '''@@ -6,7 +6,7 @@
 {
     public function login(string $email): bool
     {
-        return $email !== "";
+        return trim($email) !== "";
     }
''',
        "selected": "testLoginRejectsBlankEmail",
        "framework": "phpunit",
    },
    {
        "id": "dart",
        "production_path": "lib/auth_service.dart",
        "production": """bool login(String email) {
  return email.trim().isNotEmpty;
}

bool logout() {
  return true;
}
""",
        "test_path": "test/auth_service_test.dart",
        "tests": """import 'package:test/test.dart';
import 'package:demo/auth_service.dart';

void main() {
  test('rejects blank login', () {
    expect(login(' '), isFalse);
  });

  test('clears session on logout', () {
    expect(logout(), isTrue);
  });
}
""",
        "patch": """@@ -1,3 +1,3 @@
 bool login(String email) {
-  return email.isNotEmpty;
+  return email.trim().isNotEmpty;
 }
""",
        "selected": "rejects blank login",
        "framework": "dart_test",
    }
,
    {
        "id": "go",
        "production_path": "auth.go",
        "production": """package auth

func Login(email string) bool {
    return len(email) > 0
}

func Logout() bool {
    return true
}
""",
        "test_path": "auth_test.go",
        "tests": """package auth

import "testing"

func TestLoginRejectsBlank(t *testing.T) {
    Login(" ")
}

func TestLogoutClearsSession(t *testing.T) {
    Logout()
}
""",
        "patch": """@@ -1,5 +1,5 @@
 package auth

 func Login(email string) bool {
-    return len(email) > 0
+    return len(strings.TrimSpace(email)) > 0
 }
""",
        "selected": "TestLoginRejectsBlank",
        "framework": "go_test",
    },
    {
        "id": "elixir",
        "production_path": "lib/my_app/auth.ex",
        "production": """defmodule MyApp.Auth do
  def login(email) do
    String.trim(email) != ""
  end

  def logout() do
    true
  end
end
""",
        "test_path": "test/my_app/auth_test.exs",
        "tests": """defmodule MyApp.AuthTest do
  use ExUnit.Case
  alias MyApp.Auth

  test "rejects blank login" do
    Auth.login(" ")
  end

  test "clears session on logout" do
    Auth.logout()
  end
end
""",
        "patch": """@@ -1,5 +1,5 @@
 defmodule MyApp.Auth do
   def login(email) do
-    email != ""
+    String.trim(email) != ""
   end
""",
        "selected": "rejects blank login",
        "framework": "exunit",
    },
    {
        "id": "clojure",
        "production_path": "src/demo/auth.clj",
        "production": """(ns demo.auth)

(defn valid-login? [email]
  (not (clojure.string/blank? email)))

(defn logout []
  true)
""",
        "test_path": "test/demo/auth_test.clj",
        "tests": """(ns demo.auth-test
  (:require [clojure.test :refer [deftest is]]
            [demo.auth :as auth]))

(deftest rejects-blank-login
  (is (false? (auth/valid-login? " "))))

(deftest clears-session-on-logout
  (is (true? (auth/logout))))
""",
        "patch": """@@ -1,5 +1,5 @@
 (ns demo.auth)

 (defn valid-login? [email]
-  (not (empty? email)))
+  (not (clojure.string/blank? email)))
""",
        "selected": "rejects-blank-login",
        "framework": "clojure_test",
    },
    {
        "id": "powershell",
        "production_path": "src/Auth.psm1",
        "production": """function Test-Login {
    param([string]$Email)
    return -not [string]::IsNullOrWhiteSpace($Email)
}

function Clear-Session {
    return $true
}
""",
        "test_path": "tests/Auth.Tests.ps1",
        "tests": """Import-Module "$PSScriptRoot/../src/Auth.psm1"

Describe "Auth" {
    It "rejects blank login" {
        Test-Login -Email " " | Should -BeFalse
    }

    It "clears session on logout" {
        Clear-Session | Should -BeTrue
    }
}
""",
        "patch": """@@ -1,5 +1,5 @@
 function Test-Login {
     param([string]$Email)
-    return $Email.Length -gt 0
+    return -not [string]::IsNullOrWhiteSpace($Email)
 }
""",
        "selected": "rejects blank login",
        "framework": "pester",
    }

]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_language_adapter_selects_only_directly_affected_test(tmp_path, case):
    production = tmp_path / case["production_path"]
    production.parent.mkdir(parents=True, exist_ok=True)
    production.write_text(case["production"], encoding="utf-8")

    tests = tmp_path / case["test_path"]
    tests.parent.mkdir(parents=True, exist_ok=True)
    tests.write_text(case["tests"], encoding="utf-8")

    pull_request = GitHubPullRequest(
        owner="example",
        repo=f"{case['id']}-demo",
        number=30,
        title=f"Fix {case['id']} login validation",
        url=f"https://github.com/example/{case['id']}-demo/pull/30",
        base_sha="base",
        head_sha="head",
        changed_files=[
            GitHubChangedFile(
                path=case["production_path"],
                status="modified",
                additions=1,
                deletions=1,
                patch=case["patch"],
            )
        ],
    )

    result = PullRequestAnalysisService().analyse_repository(
        pull_request, tmp_path
    )

    assert result.selection_mode == "targeted"
    assert result.total_tests_discovered == 2
    assert [test.test_name for test in result.recommended_tests] == [
        case["selected"]
    ]
    assert result.recommended_tests[0].framework == case["framework"]
