from app.services.language_support import (
    analyse_source_impact,
    build_repository_import_graph,
    discover_repository_tests,
)


def test_discovers_vitest_tests_with_imports_and_direct_calls(tmp_path):
    (tmp_path / "package.json").write_text(
        '{"devDependencies": {"vitest": "latest"}}',
        encoding="utf-8",
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "auth.test.ts").write_text(
        '''import { login, logout } from "../src/auth";

test("login trims email", () => {
  expect(login(" example@test.com ")).toBe("example@test.com");
});

it("logout clears session", () => {
  expect(logout()).toBe(true);
});
''',
        encoding="utf-8",
    )

    discovered = discover_repository_tests(tmp_path)

    assert [test["test_name"] for test in discovered] == [
        "login trims email",
        "logout clears session",
    ]
    assert all(test["framework"] == "vitest" for test in discovered)
    assert all(test["imports"] == ["src/auth"] for test in discovered)
    assert discovered[0]["called_names"] == ["login", "toBe"]
    assert discovered[1]["called_names"] == ["logout", "toBe"]


def test_discovers_junit_tests_with_imports_and_direct_calls(tmp_path):
    test_dir = tmp_path / "src" / "test" / "java" / "com" / "example"
    test_dir.mkdir(parents=True)
    (test_dir / "AuthServiceTest.java").write_text(
        '''package com.example;

import com.example.AuthService;
import org.junit.jupiter.api.Test;

class AuthServiceTest {
    @Test
    void loginSucceeds() {
        service.login("person@example.com");
    }

    @Test
    void logoutClearsSession() {
        service.logout();
    }
}
''',
        encoding="utf-8",
    )

    discovered = discover_repository_tests(tmp_path)

    assert [test["test_name"] for test in discovered] == [
        "loginSucceeds",
        "logoutClearsSession",
    ]
    assert all(test["framework"] == "junit" for test in discovered)
    assert "com.example.AuthService" in discovered[0]["imports"]
    assert discovered[0]["called_names"] == ["login"]


def test_javascript_impact_maps_changed_line_to_function():
    source = '''export function login(email: string) {
  const normalised = email.trim();
  return normalised;
}

export function logout() {
  return true;
}
'''

    impact = analyse_source_impact("javascript", source, [2])

    assert impact["changed_functions"] == ["login"]
    assert impact["changed_classes"] == []
    assert impact["module_level_change"] is False


def test_java_impact_maps_changed_line_to_method_and_class():
    source = '''package com.example;

public class AuthService {
    public boolean login(String email) {
        return email != null;
    }

    public boolean logout() {
        return true;
    }
}
'''

    impact = analyse_source_impact("java", source, [5])

    assert impact["changed_functions"] == ["login"]
    assert impact["changed_classes"] == ["AuthService"]
    assert impact["module_level_change"] is False


def test_cross_language_import_graph_resolves_local_modules(tmp_path):
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "auth.ts").write_text(
        "export function login() { return true; }\n",
        encoding="utf-8",
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "auth.test.ts").write_text(
        'import { login } from "../src/auth";\ntest("login", () => login());\n',
        encoding="utf-8",
    )

    graph, modules = build_repository_import_graph(tmp_path)

    assert modules["src/auth.ts"] == "src/auth"
    assert graph["tests/auth.test"] == {"src/auth"}



def test_typescript_class_method_with_return_type_is_mapped():
    source = '''export class AuthService {
  public login(email: string): boolean {
    return email.trim().length > 0;
  }

  public logout(): boolean {
    return true;
  }
}
'''

    impact = analyse_source_impact("javascript", source, [3])

    assert impact["changed_functions"] == ["login"]
    assert impact["changed_classes"] == ["AuthService"]
    assert impact["module_level_change"] is False


def test_nested_javascript_package_detects_mocha(tmp_path):
    package = tmp_path / "packages" / "accounts"
    tests = package / "test"
    tests.mkdir(parents=True)
    (package / "package.json").write_text(
        '{"devDependencies": {"mocha": "latest"}}',
        encoding="utf-8",
    )
    (tests / "auth.spec.js").write_text(
        'it("logs in", function () { login(); });\n',
        encoding="utf-8",
    )

    discovered = discover_repository_tests(tmp_path)

    assert len(discovered) == 1
    assert discovered[0]["framework"] == "mocha"



def test_discovers_kotlin_junit_test_and_maps_method(tmp_path):
    test_dir = tmp_path / "src" / "test" / "kotlin" / "demo"
    test_dir.mkdir(parents=True)
    (test_dir / "AuthServiceTest.kt").write_text(
        '''package demo

import org.junit.jupiter.api.Test

class AuthServiceTest {
    @Test
    fun loginRejectsBlankEmail() {
        service.login(" ")
    }
}
''',
        encoding="utf-8",
    )
    discovered = discover_repository_tests(tmp_path)

    assert len(discovered) == 1
    assert discovered[0]["framework"] == "junit"
    assert discovered[0]["test_name"] == "loginRejectsBlankEmail"
    assert discovered[0]["called_names"] == ["login"]

    impact = analyse_source_impact(
        "kotlin",
        '''package demo

class AuthService {
    fun login(email: String): Boolean {
        return email.isNotBlank()
    }
}
''',
        [5],
    )
    assert impact["changed_functions"] == ["login"]
    assert impact["changed_classes"] == ["AuthService"]
    assert impact["module_level_change"] is False


def test_discovers_xunit_test_and_maps_csharp_method(tmp_path):
    tests = tmp_path / "Demo.Tests"
    tests.mkdir()
    (tests / "AuthServiceTests.cs").write_text(
        '''using Demo.Services;
using Xunit;

namespace Demo.Tests;

public class AuthServiceTests
{
    [Fact]
    public void LoginRejectsBlankEmail()
    {
        service.Login(" ");
    }
}
''',
        encoding="utf-8",
    )
    discovered = discover_repository_tests(tmp_path)

    assert len(discovered) == 1
    assert discovered[0]["framework"] == "xunit"
    assert discovered[0]["test_name"] == "LoginRejectsBlankEmail"
    assert discovered[0]["imports"] == ["Demo.Services", "Xunit"]
    assert discovered[0]["called_names"] == ["Login"]

    impact = analyse_source_impact(
        "csharp",
        '''namespace Demo.Services;

public class AuthService
{
    public bool Login(string email)
    {
        return !string.IsNullOrWhiteSpace(email);
    }
}
''',
        [7],
    )
    assert impact["changed_functions"] == ["Login"]
    assert impact["changed_classes"] == ["AuthService"]
    assert impact["module_level_change"] is False


def test_discovers_rspec_example_and_maps_ruby_method(tmp_path):
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "auth_service.rb").write_text(
        '''class AuthService
  def login(email)
    !email.strip.empty?
  end
end
''',
        encoding="utf-8",
    )
    specs = tmp_path / "spec"
    specs.mkdir()
    (specs / "auth_service_spec.rb").write_text(
        '''require_relative "../lib/auth_service"

RSpec.describe AuthService do
  it "rejects blank login" do
    expect(AuthService.new.login(" ")).to be(false)
  end
end
''',
        encoding="utf-8",
    )
    discovered = discover_repository_tests(tmp_path)

    assert len(discovered) == 1
    assert discovered[0]["framework"] == "rspec"
    assert discovered[0]["test_name"] == "rejects blank login"
    assert discovered[0]["imports"] == ["auth_service"]
    assert "login" in discovered[0]["called_names"]

    impact = analyse_source_impact(
        "ruby",
        (lib / "auth_service.rb").read_text(encoding="utf-8"),
        [3],
    )
    assert impact["changed_functions"] == ["login"]
    assert impact["changed_classes"] == ["AuthService"]
    assert impact["module_level_change"] is False


def test_discovers_phpunit_test_and_maps_php_method(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "AuthServiceTest.php").write_text(
        '''<?php

namespace Tests;

use App\\Services\\AuthService;

class AuthServiceTest
{
    public function testLoginRejectsBlankEmail(): void
    {
        $service->login(" ");
    }
}
''',
        encoding="utf-8",
    )
    discovered = discover_repository_tests(tmp_path)

    assert len(discovered) == 1
    assert discovered[0]["framework"] == "phpunit"
    assert discovered[0]["test_name"] == "testLoginRejectsBlankEmail"
    assert discovered[0]["imports"] == ["App.Services.AuthService"]
    assert discovered[0]["called_names"] == ["login"]

    impact = analyse_source_impact(
        "php",
        '''<?php

namespace App\\Services;

class AuthService
{
    public function login(string $email): bool
    {
        return trim($email) !== "";
    }
}
''',
        [9],
    )
    assert impact["changed_functions"] == ["login"]
    assert impact["changed_classes"] == ["AuthService"]
    assert impact["module_level_change"] is False



def test_discovers_dart_test_and_maps_function(tmp_path):
    tests = tmp_path / "test"
    tests.mkdir()
    (tests / "auth_service_test.dart").write_text(
        '''import 'package:test/test.dart';
import 'package:demo/auth_service.dart';

void main() {
  test('rejects blank login', () {
    expect(login(' '), isFalse);
  });
}
''',
        encoding="utf-8",
    )
    discovered = discover_repository_tests(tmp_path)

    assert len(discovered) == 1
    assert discovered[0]["framework"] == "dart_test"
    assert discovered[0]["test_name"] == "rejects blank login"
    assert "auth_service" in discovered[0]["imports"]
    assert "login" in discovered[0]["called_names"]

    impact = analyse_source_impact(
        "dart",
        '''bool login(String email) {
  return email.trim().isNotEmpty;
}

bool logout() {
  return true;
}
''',
        [2],
    )
    assert impact["changed_functions"] == ["login"]
    assert impact["module_level_change"] is False



def test_dart_barrel_export_is_included_in_import_graph(tmp_path):
    source = tmp_path / "lib" / "src"
    source.mkdir(parents=True)
    (tmp_path / "lib" / "collection.dart").write_text(
        "export 'src/list_extensions.dart';\n",
        encoding="utf-8",
    )
    (source / "list_extensions.dart").write_text(
        "List<int> slice(List<int> values) { return values; }\n",
        encoding="utf-8",
    )

    graph, _ = build_repository_import_graph(tmp_path)

    assert "src/list_extensions" in graph["collection"]


def test_discovers_go_tests_and_maps_function(tmp_path):
    (tmp_path / "auth_test.go").write_text(
        '''package auth

import "testing"

func TestLoginRejectsBlank(t *testing.T) {
    Login(" ")
}

func TestLogoutClearsSession(t *testing.T) {
    Logout()
}
''',
        encoding="utf-8",
    )
    discovered = discover_repository_tests(tmp_path)

    assert [test["test_name"] for test in discovered] == [
        "TestLoginRejectsBlank",
        "TestLogoutClearsSession",
    ]
    assert all(test["framework"] == "go_test" for test in discovered)
    assert "auth" in discovered[0]["imports"]
    assert discovered[0]["called_names"] == ["Login"]

    impact = analyse_source_impact(
        "go",
        '''package auth

func Login(email string) bool {
    return len(email) > 0
}

func Logout() bool {
    return true
}
''',
        [4],
    )
    assert impact["changed_functions"] == ["Login"]
    assert impact["module_level_change"] is False


def test_discovers_exunit_tests_and_maps_function(tmp_path):
    tests = tmp_path / "test"
    tests.mkdir()
    (tests / "auth_test.exs").write_text(
        '''defmodule MyApp.AuthTest do
  use ExUnit.Case
  alias MyApp.Auth

  test "rejects blank login" do
    Auth.login(" ")
  end
end
''',
        encoding="utf-8",
    )
    discovered = discover_repository_tests(tmp_path)

    assert len(discovered) == 1
    assert discovered[0]["framework"] == "exunit"
    assert discovered[0]["test_name"] == "rejects blank login"
    assert "MyApp.Auth" in discovered[0]["imports"]
    assert discovered[0]["called_names"] == ["login"]

    impact = analyse_source_impact(
        "elixir",
        '''defmodule MyApp.Auth do
  def login(email) do
    String.trim(email) != ""
  end
end
''',
        [3],
    )
    assert impact["changed_functions"] == ["login"]
    assert impact["changed_classes"] == ["MyApp.Auth"]
    assert impact["module_level_change"] is False


def test_elixir_multiline_private_function_is_mapped_precisely():
    impact = analyse_source_impact(
        "elixir",
        """defmodule Ecto.Type do
  defp cast_naive_datetime(
         <<year::4-bytes, ?-, month::2-bytes>>
       )
       when month != "00" do
    {year, month}
  end

  defp unchanged(value), do: value
end
""",
        [6],
    )

    assert impact["changed_functions"] == ["cast_naive_datetime"]
    assert impact["changed_classes"] == ["Ecto.Type"]
    assert impact["module_level_change"] is False


def test_discovers_clojure_tests_and_maps_function(tmp_path):
    tests = tmp_path / "test" / "demo"
    tests.mkdir(parents=True)
    (tests / "auth_test.clj").write_text(
        '''(ns demo.auth-test
  (:require [clojure.test :refer [deftest is]]
            [demo.auth :as auth]))

(deftest rejects-blank-login
  (is (false? (auth/valid-login? " "))))
''',
        encoding="utf-8",
    )
    discovered = discover_repository_tests(tmp_path)

    assert len(discovered) == 1
    assert discovered[0]["framework"] == "clojure_test"
    assert discovered[0]["test_name"] == "rejects-blank-login"
    assert "demo.auth" in discovered[0]["imports"]
    assert "valid-login?" in discovered[0]["called_names"]

    impact = analyse_source_impact(
        "clojure",
        '''(ns demo.auth)

(defn valid-login? [email]
  (not (clojure.string/blank? email)))

(defn logout []
  true)
''',
        [4],
    )
    assert impact["changed_functions"] == ["valid-login?"]
    assert impact["module_level_change"] is False


def test_discovers_pester_tests_and_maps_function(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "Auth.Tests.ps1").write_text(
        '''Import-Module "$PSScriptRoot/../src/Auth.psm1"

Describe "Auth" {
    It "rejects blank login" {
        Test-Login -Email " " | Should -BeFalse
    }
}
''',
        encoding="utf-8",
    )
    discovered = discover_repository_tests(tmp_path)

    assert len(discovered) == 1
    assert discovered[0]["framework"] == "pester"
    assert discovered[0]["test_name"] == "rejects blank login"
    assert discovered[0]["imports"] == ["src/Auth"]
    assert discovered[0]["called_names"] == ["Test-Login"]

    impact = analyse_source_impact(
        "powershell",
        '''function Test-Login {
    param([string]$Email)
    return -not [string]::IsNullOrWhiteSpace($Email)
}

function Clear-Session {
    return $true
}
''',
        [3],
    )
    assert impact["changed_functions"] == ["Test-Login"]
    assert impact["module_level_change"] is False
