#pragma once
struct TextParser { TextParser(const char*) {} template<class... T> void parseLine(char*, T&...) {} };
