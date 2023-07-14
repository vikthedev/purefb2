import shlex

if 'с иллюстрациями' in text or '+img' in text:
            img = ''

        if 'zelluloza.ru' in url:
            download_link = f'{Elib2Ebook_zelluloza} -f fb2' + url_cmd + login_password + img
        else:
            download_link = f'{Elib2Ebook} -f fb2' + url_cmd + login_password + img

        args = shlex.split(download_link)

        file_name_raw = None
        try:
            output = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = output.communicate()
            if output.returncode != 0:
                if 'Неверный логин или пароль' in stderr.decode() and 'author.today' in url:
                    sql = ('delete from accounts '
                           'where account_id = ?')
                    params = (account_id,)
                    execute_sql(books_db, sql, params)

                    sql = ('delete from urls '
                           'where account_id = ?')
                    params = (account_id,)
                    execute_sql(books_db, sql, params)

                    send_text = f'Не удалось авторизоваться, неверный логин или пароль: {url}'
                else:
                    send_text = (f'Не удалось обработать: {url}. '
                                 f'Попробуйте позже или проверьте действительность логина и пароля')
                await context.bot.send_message(chat_id=chat_id, text=send_text)
            else:
                file_name_raw = re.findall(r'(?<=Книга \").*(?=\" успешно сохранена)', stdout.decode())
        except Exception:
            pass

        if file_name_raw:
            file_name_raw = file_name_raw[0]
            file = Fb2(str(file_name_raw), str(login))
            file_title, send_caption, isFinished = file.processing()