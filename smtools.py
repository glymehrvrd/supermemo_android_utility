#coding=utf-8
#!/usr/bin/python
from struct import pack, unpack
import zlib
import os
import sqlite3
from xml.etree import ElementTree
import time


class sm2phone():
    def enc(self, inp):
        '''Encode uint to variant byte encoding'''
        outp = []
        k = 128
        while(True):
            flag = 0 if (inp / 256) == 0 else 1
            outp.append(inp & 127 + flag * k)
            k = k * 128
            inp = inp / 128
            if(flag != 1):
                return outp

    def checkPath(self, path):
        '''Check a path and create it if not exists'''

        parts = path.split('/')
        if(len(parts) == 1):
            return
        tmppath = ""
        for i in range(0, len(parts) - 1):
            tmppath += parts[i] + '/'
            if(not os.path.isdir(tmppath)):
                os.mkdir(tmppath)

    def read_header(self, f):
        '''read the header of smpak'''

        header_data = f.read(20)
        if header_data[:8] != "-SMArch-":
            exit()
        self.entry_chk_offset, = unpack('I', header_data[12:16])
        print self.entry_chk_offset
        self.name_chk_offset, = unpack('I', header_data[16:20])

    def read_entries(self, f):
        '''read the entries of smpak'''

        f.seek(self.entry_chk_offset)
        entry_count, = unpack("I", f.read(4))
        self.entries = []
        for i in range(entry_count):
            self.entry = {}
            self.entry["name_offset"], = unpack("I", f.read(4))
            self.entry["name_length"], = unpack("H", f.read(2))
            self.entry["mode"], = unpack("H", f.read(2))
            self.entry["data_offset"], = unpack("I", f.read(4))
            self.entry["data_size"], = unpack("I", f.read(4))
            self.entries.append(self.entry)

    def read_names(self, f):
        '''read the names of smpak'''

        f.seek(self.name_chk_offset)
        name_size, = unpack("I", f.read(4))
        f.seek(-name_size, 2)
        name_begin = f.tell()
        for self.entry in self.entries:
            f.seek(name_begin + self.entry["name_offset"])
            self.entry_name = f.read(self.entry["name_length"])
            self.entry["name"] = self.entry_name

    def read_data(self, f):
        '''read the datas of smpak'''

        for self.entry in self.entries:
            print self.entry["name"]
            f.seek(self.entry["data_offset"])
            fdata = f.read(self.entry["data_size"])
            if self.entry["mode"] == 1:
                fdata = zlib.decompress(fdata, -15)
                yield fdata

    def unpack(self, path, output_path=''):
        '''unpack smpak\n
        if output_path is empty, a generator of file data will be returned'''

        if(output_path[-1] != '\\'):
            output_path += '\\'
        output_path = output_path.replace('\\', '/')
        self.checkPath(output_path)

        with open(path, "rb") as f:
            self.read_header(f)
            self.read_entries(f)
            self.read_names(f)
            fdatas = self.read_data(f)
            if(output_path == ''):
                return fdatas
            else:
                for fdata in fdatas:
                    self.checkPath(output_path + self.entry['name'])
                    with open(output_path + self.entry["name"], "wb") as entry_file:
                        entry_file.write(fdata)

    def pack(self, path, output_file):
        with open(output_file, 'wb') as f:
            #header
            f.write(pack('8s', '-SMArch-'))     # sign
            f.write(pack('H', 0x0101))          # version
            f.write(pack('H', 0))               # lock
            entry_chk_offset = 0x0101           # fill it later
            name_chk_offset = 0
            f.write(pack('I', entry_chk_offset))
            f.write(pack('I', name_chk_offset))

            #data
            entries = []
            filelist = []   # course files
            for root, dirs, files in os.walk(path):
                for name in files:
                    filelist.append(os.path.join(root, name))
            filelist.sort()

            short_names = ""
            for data_file in filelist:
                short_name = data_file.replace(path, '').replace('\\', '/').lower()

                with open(data_file, 'rb') as fd:
                    fdata = fd.read()
                iszip = (data_file[-4:] in ('.xml', '.css'))
                if(iszip):
                    fdata = zlib.compress(fdata)[2:]

                f.write(pack('8s', 'DataChnk'))
                data_offset = f.tell()
                f.write(fdata)

                entries.append({
                    'name_offset': pack('I', len(short_names)),
                    'name_length': pack('H', len(short_name)),
                    'flag': pack('H', 1) if iszip else pack('H', 0),
                    'data_offset': pack('I', data_offset),
                    'data_size': pack('I', len(fdata))
                    })
                short_names += short_name

            #entries
            f.write('EntrChnk')
            entry_chk_offset = f.tell()
            entry_count = len(entries)
            f.write(pack('I', entry_count))
            for entry in entries:
                f.write(entry['name_offset'])
                f.write(entry['name_length'])
                f.write(entry['flag'])
                f.write(entry['data_offset'])
                f.write(entry['data_size'])

            #names
            f.write('NameChnk')
            name_chk_offset = f.tell()
            print len(short_names)
            print short_names
            f.write(pack('I', len(short_names)))
            for vbe in self.enc(len(short_names)):
                f.write(pack('B', vbe))
            f.write(short_names)

            #missing offsets
            f.seek(12)
            f.write(pack('I', entry_chk_offset))
            f.write(pack('I', name_chk_offset))

    def createDefaultTables(self, db):
        c = db.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS CourseDescriptions ( CourseId integer NOT NULL ON CONFLICT ROLLBACK, Value text NOT NULL ON CONFLICT REPLACE DEFAULT '', Lang smallint NOT NULL ON CONFLICT REPLACE DEFAULT 0, PRIMARY KEY(CourseId, Lang));''')
        c.execute('''CREATE TABLE IF NOT EXISTS Courses ( Id integer PRIMARY KEY AUTOINCREMENT NOT NULL UNIQUE ON CONFLICT ROLLBACK, Guid text NOT NULL ON CONFLICT ROLLBACK UNIQUE, Version integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Title text NOT NULL ON CONFLICT REPLACE DEFAULT '', LangSource integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, LangTaught integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, LangTranslations integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Type integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Path text NOT NULL ON CONFLICT REPLACE DEFAULT '', Author text NOT NULL ON CONFLICT REPLACE DEFAULT '', RightsOwner text NOT NULL ON CONFLICT REPLACE DEFAULT '', Translators text NOT NULL ON CONFLICT REPLACE DEFAULT '', BoxLink text NOT NULL ON CONFLICT REPLACE DEFAULT '', Created bigint NOT NULL ON CONFLICT REPLACE DEFAULT 0, Modified bigint NOT NULL ON CONFLICT REPLACE DEFAULT 0, DefItemsPerDay integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, DefTemplateId integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Subscribed bigint NOT NULL ON CONFLICT REPLACE DEFAULT 0, ItemsPerDay smallint NOT NULL ON CONFLICT REPLACE DEFAULT 30, Today integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, TodayDone smallint NOT NULL ON CONFLICT REPLACE DEFAULT 0, LastPageNum integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, RequestedFI float(10) NOT NULL ON CONFLICT REPLACE DEFAULT 10, OptRec blob, TotalPages integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, InactivePages integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, ExercisePages integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, PagesDone integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, LastSynchro bigint NOT NULL ON CONFLICT REPLACE DEFAULT 0, LastFreeDaysUpdate bigint NOT NULL ON CONFLICT REPLACE DEFAULT 0, LastServerUpdate bigint NOT NULL ON CONFLICT REPLACE DEFAULT 0, Flags smallint NOT NULL ON CONFLICT REPLACE DEFAULT 0, MenuOrder smallint NOT NULL ON CONFLICT REPLACE DEFAULT 0, FontSize smallint NOT NULL ON CONFLICT REPLACE DEFAULT 0, FontSizeQuestion smallint NOT NULL ON CONFLICT REPLACE DEFAULT 0, FontSizeAnswer smallint NOT NULL ON CONFLICT REPLACE DEFAULT 0, ProductId integer NOT NULL ON CONFLICT REPLACE DEFAULT 0);''')
        c.execute('''CREATE TABLE IF NOT EXISTS DeletedItems (CourseId integer NOT NULL ON CONFLICT ROLLBACK, PageNum integer NOT NULL ON CONFLICT ROLLBACK, Date bigint NOT NULL ON CONFLICT REPLACE DEFAULT 0, ParentNum integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, PrevNum integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, PRIMARY KEY(CourseId, PageNum));''')
        c.execute('''CREATE TABLE IF NOT EXISTS ExamItems (ExamId integer NOT NULL ON CONFLICT ROLLBACK, PageNum integer NOT NULL ON CONFLICT ROLLBACK, Answers text, PRIMARY KEY(ExamId, PageNum));''')
        c.execute('''CREATE TABLE IF NOT EXISTS Exams (Id integer PRIMARY KEY AUTOINCREMENT NOT NULL ON CONFLICT ROLLBACK, CourseId integer NOT NULL ON CONFLICT ROLLBACK, MainPageNum integer NOT NULL ON CONFLICT ROLLBACK, Points integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, MaxPoints integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Attempt integer NOT NULL ON CONFLICT REPLACE DEFAULT 0);''')
        c.execute('''CREATE TABLE IF NOT EXISTS Fingerprints2 ( Id integer PRIMARY KEY AUTOINCREMENT NOT NULL UNIQUE ON CONFLICT ROLLBACK, Data blob, ActivateHash text);''')
        c.execute('''CREATE TABLE IF NOT EXISTS FreeDays (CourseId integer NOT NULL ON CONFLICT ROLLBACK, Day integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, PRIMARY KEY(CourseId, Day));''')
        c.execute('''CREATE TABLE IF NOT EXISTS FreeWeekDays (CourseId integer NOT NULL ON CONFLICT ROLLBACK, Flags integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, PRIMARY KEY(CourseId));''')
        c.execute('''CREATE TABLE IF NOT EXISTS GlossaryPhrases (Id integer NOT NULL ON CONFLICT ROLLBACK, CourseId integer NOT NULL ON CONFLICT ROLLBACK, ParentId integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Key text, Value text, Type text, Type2 text, File text, Reverse boolean NOT NULL ON CONFLICT REPLACE DEFAULT 0, PRIMARY KEY(CourseId, Id));''')
        c.execute('''CREATE TABLE IF NOT EXISTS Items ( CourseId integer NOT NULL ON CONFLICT ROLLBACK, PageNum integer NOT NULL ON CONFLICT ROLLBACK, ParentNum integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, PrevNum integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, TemplateId integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Type smallint NOT NULL ON CONFLICT REPLACE DEFAULT 0, Disabled boolean NOT NULL ON CONFLICT REPLACE DEFAULT 0, Keywords text NOT NULL ON CONFLICT REPLACE DEFAULT '', PartOfSpeech text NOT NULL ON CONFLICT REPLACE DEFAULT '', Frequency integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Name text NOT NULL ON CONFLICT ROLLBACK, Modified bigint NOT NULL ON CONFLICT REPLACE DEFAULT 0, ChapterTitle text, LessonTitle text, Command text, Question text, Answer text, QuestionAudio boolean NOT NULL ON CONFLICT REPLACE DEFAULT 0, AnswerAudio boolean NOT NULL ON CONFLICT REPLACE DEFAULT 0, ExamPoints smallint NOT NULL ON CONFLICT REPLACE DEFAULT 0, Gfx1Id integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Gfx1GroupId integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Gfx1Shuffle boolean NOT NULL ON CONFLICT REPLACE DEFAULT 0, Gfx2Id integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Gfx2GroupId integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Gfx2Shuffle boolean NOT NULL ON CONFLICT REPLACE DEFAULT 0, Gfx3Id integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Gfx3GroupId integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Gfx3Shuffle boolean NOT NULL ON CONFLICT REPLACE DEFAULT 0, QueueOrder integer NOT NULL ON CONFLICT REPLACE DEFAULT 1, Status smallint NOT NULL ON CONFLICT REPLACE DEFAULT 0, LastRepetition integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, NextRepetition integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, AFactor float(10,2) NOT NULL ON CONFLICT REPLACE DEFAULT 3, EstimatedFI float(10) NOT NULL ON CONFLICT REPLACE DEFAULT 0, ExpectedFI float(10) NOT NULL ON CONFLICT REPLACE DEFAULT 0, FirstGrade smallint NOT NULL ON CONFLICT REPLACE DEFAULT 6, Flags smallint NOT NULL ON CONFLICT REPLACE DEFAULT 0, Grades int NOT NULL ON CONFLICT REPLACE DEFAULT 0, Lapses smallint NOT NULL ON CONFLICT REPLACE DEFAULT 0, NewInterval integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, NormalizedGrade float NOT NULL ON CONFLICT REPLACE DEFAULT 0, Repetitions smallint NOT NULL ON CONFLICT REPLACE DEFAULT 0, RepetitionsCategory smallint NOT NULL ON CONFLICT REPLACE DEFAULT 0, UFactor float(10,2) NOT NULL ON CONFLICT REPLACE DEFAULT 0, UsedInterval integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, OrigNewInterval integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, SubSet text, SubType text, PRIMARY KEY(CourseId, PageNum));''')
        c.execute('''CREATE TABLE IF NOT EXISTS LearnStats (CourseId integer NOT NULL ON CONFLICT ROLLBACK, Day integer NOT NULL ON CONFLICT ROLLBACK, AllPagesDone integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, NewPagesDone integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, RepsDone integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, RepsLeft integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Lapses integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, AllRepsDone integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, PRIMARY KEY(CourseId, Day));''')
        c.execute('''CREATE TABLE IF NOT EXISTS Notes ( CourseId integer NOT NULL ON CONFLICT ROLLBACK, PageNum integer NOT NULL ON CONFLICT ROLLBACK, X smallint NOT NULL ON CONFLICT REPLACE DEFAULT 0, Y smallint NOT NULL ON CONFLICT REPLACE DEFAULT 0, Width integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Height integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Text text NOT NULL ON CONFLICT REPLACE DEFAULT '', Visible bool NOT NULL ON CONFLICT REPLACE DEFAULT 0, PRIMARY KEY(CourseId, PageNum));''')
        c.execute('''CREATE TABLE IF NOT EXISTS StoreCourses ( Id integer NOT NULL ON CONFLICT ROLLBACK, ParentId integer NOT NULL ON CONFLICT ROLLBACK, FolderId integer NOT NULL ON CONFLICT ROLLBACK, Name text NOT NULL ON CONFLICT REPLACE DEFAULT '', Subtitle text NOT NULL ON CONFLICT REPLACE DEFAULT '', Teaser text NOT NULL ON CONFLICT REPLACE DEFAULT '', ProductId integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, LangSrc integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, LangTaught integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Icon text NOT NULL ON CONFLICT REPLACE DEFAULT '', Url text NOT NULL ON CONFLICT REPLACE DEFAULT '', Guid text NOT NULL ON CONFLICT REPLACE DEFAULT '', IsFree boolean NOT NULL ON CONFLICT REPLACE DEFAULT 0, IsNew boolean NOT NULL ON CONFLICT REPLACE DEFAULT 0, Discount integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Price text NOT NULL ON CONFLICT REPLACE DEFAULT '', PriceValue float(10) NOT NULL ON CONFLICT REPLACE DEFAULT 0, PriceCurrency text NOT NULL ON CONFLICT REPLACE DEFAULT '', Version integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Rank integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Size integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, StoreUrl text NOT NULL ON CONFLICT REPLACE DEFAULT '', Weight integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, PRIMARY KEY(Id, FolderId));''')
        c.execute('''CREATE TABLE IF NOT EXISTS StoreDescriptions ( Guid text NOT NULL ON CONFLICT ROLLBACK UNIQUE, Lang integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Value text NOT NULL ON CONFLICT REPLACE DEFAULT '',Updated bigint NOT NULL ON CONFLICT REPLACE DEFAULT 0, PRIMARY KEY(Guid, Lang));''')
        c.execute('''CREATE TABLE IF NOT EXISTS StoreFolders ( Id integer PRIMARY KEY AUTOINCREMENT NOT NULL UNIQUE ON CONFLICT ROLLBACK, ParentId integer NOT NULL ON CONFLICT ROLLBACK, Name text NOT NULL ON CONFLICT REPLACE DEFAULT '', Icon text NOT NULL ON CONFLICT REPLACE DEFAULT '', Weight integer NOT NULL ON CONFLICT REPLACE DEFAULT 0);''')
        c.execute('''CREATE TABLE IF NOT EXISTS Version ( Major integer NOT NULL ON CONFLICT REPLACE DEFAULT 0, Minor integer NOT NULL ON CONFLICT REPLACE DEFAULT 0 );''')
        c.execute('''CREATE TABLE IF NOT EXISTS android_metadata (locale TEXT);''')
        c.execute('''CREATE INDEX IF NOT EXISTS c1 ON Courses (Type, LangTaught);''')
        c.execute('''CREATE UNIQUE INDEX IF NOT EXISTS fp1 ON Fingerprints2 (ActivateHash);''')
        c.execute('''CREATE INDEX IF NOT EXISTS gp1 ON GlossaryPhrases (CourseId, ParentId, Reverse);''')
        c.execute('''CREATE INDEX IF NOT EXISTS i1 ON Items (CourseId, Type);''')
        c.execute('''CREATE INDEX IF NOT EXISTS i2 ON Items (CourseId, ParentNum);''')
        c.execute('''CREATE INDEX IF NOT EXISTS i3 ON Items (CourseId, Disabled, Status, NextRepetition);''')
        c.execute('''CREATE INDEX IF NOT EXISTS i4 ON Items (Keywords);''')
        c.execute('''CREATE INDEX IF NOT EXISTS i5 ON Items (CourseId, Disabled, QueueOrder);''')
        c.execute('''CREATE INDEX IF NOT EXISTS i6 ON Items (CourseId, PageNum);''')
        c.execute('''CREATE INDEX IF NOT EXISTS sc1 ON StoreCourses (FolderId);''')
        c.execute('''CREATE INDEX IF NOT EXISTS sc2 ON StoreCourses (ParentId);''')
        c.execute('''CREATE INDEX IF NOT EXISTS sc3 ON StoreCourses (Guid);''')
        c.execute('''CREATE UNIQUE INDEX IF NOT EXISTS sd1 ON StoreDescriptions (Guid);''')
        c.execute('''CREATE INDEX IF NOT EXISTS sf1 ON StoreFolders (ParentId);''')
        c.close()

    def readCourseXml(self, path):
        '''read course.xml'''

        with open(path, 'rb') as f:
            self.read_header(f)

            #seek name chnk
            f.seek(self.name_chk_offset)
            name_size, = unpack("I", f.read(4))
            f.seek(-name_size, 2)
            course_str = f.read(len('course.xml'))
            if(course_str != 'course.xml'):
                print 'malformat'
                exit()

            #seek entry chnk
            f.seek(self.entry_chk_offset + 10)
            mode, = unpack('H', f.read(2))
            course_offset, = unpack('I', f.read(4))
            course_size, = unpack('I', f.read(4))

            #seek course data
            f.seek(course_offset)
            course_data = f.read(course_size)
            if(mode == 1):
                course_data = zlib.decompress(course_data, -15)

            #get course information
            root = ElementTree.fromstring(course_data)
            course_info = {}
            course_info['Guid'] = root.find('{http://www.supermemo.net/2006/smux}guid').text
            course_info['Title'] = root.find('{http://www.supermemo.net/2006/smux}title').text
            course_info['Created'] = root.find('{http://www.supermemo.net/2006/smux}created').text
            course_info['Modified'] = root.find('{http://www.supermemo.net/2006/smux}modified').text
            course_info['DefItemsPerDay'] = root.find('{http://www.supermemo.net/2006/smux}default-items-per-day').text
            course_info['Author'] = root.find('{http://www.supermemo.net/2006/smux}author').text
            course_info['RightsOwner'] = root.find('{http://www.supermemo.net/2006/smux}rights-owner').text
            course_info['BoxLink'] = root.find('{http://www.supermemo.net/2006/smux}box-link').text
            course_info['Created'] = unicode(int(time.mktime(time.strptime(course_info['Created'], '%Y-%m-%d'))))
            course_info['Modified'] = unicode(int(time.mktime(time.strptime(course_info['Modified'], '%Y-%m-%d'))))
            course_info['Path'] = ('/mnt/sdcard/Android/data/pl.supermemo/files/%s/course.smpak' % course_info['Guid'])
            description = root.find('{http://www.supermemo.net/2006/smux}description').text

            return course_info, description

    def writedb(self, path_smpak, path_db):
        '''Write specific database with given smpak'''

        db = sqlite3.connect(path_db)
        # create default tables
        self.createDefaultTables(db)

        # write table Courses, CourseDescription
        course_info, descr = self.readCourseXml(path_smpak)
        c = db.cursor()
        c.execute('INSERT INTO Courses (%s) VALUES (?,?,?,?,?,?,?,?,?)' % ','.join(course_info.keys()), course_info.values())
        c.execute('SELECT MAX(CourseId) FROM CourseDescriptions')
        max_courseid, = c.fetchone()
        max_courseid = 0 if max_courseid == None else max_courseid + 1
        c.execute('INSERT INTO CourseDescriptions (CourseId, Value, Lang) VALUES (?,?,?)', (max_courseid, descr, 0))
        db.commit()

        # write table Items
        c.close()
        db.close()

a = sm2phone()
#db = sqlite3.connect('e:\\test.db3')
#a.readCourseXml('d:\SuperMemo UX\courses\gre-zuixin\course1.smpak')
#a.writedb('d:\\SuperMemo UX\\courses\\testcourse\\course1.smpak', 'd:\\SuperMemo UX\\courses\\testcourse\\test.db')
#a.unpack(u'd:\\SuperMemo UX\\courses\\testcourse\\course.smpak', u'd:\\SuperMemo UX\\courses\\testcourse\\override\\')
a.pack(u'd:\\SuperMemo UX\\courses\\testcourse\\override\\', u'd:\\SuperMemo UX\\courses\\testcourse\\course1.smpak')
