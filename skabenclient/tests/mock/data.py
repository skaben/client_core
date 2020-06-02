
base_config = {'str': {'device': 'testing',
                      'list_one': ['one', 'two', {'3': 'number'}],
                      'list_two': [('this', 'is', 'not'), 'is', 'conf']},
              'int': {'device': 1,
                      'assume': [-2, 3.3, {'null': 0}]},
              'bool': {'device': True,
                       'blocked': False}
}

yaml_content = """
play: false
sound_files:
  dva:
    current: false
    file: 2.ogg
    loaded: true
    remote: url://
    repeat: 
      test: 1
      retest: 2
      hard_list:
       - a
       - b
       - c
  odin:
    current: false
    file: 1.ogg
    loaded: true
    remote: url://
    repeat: '2'
uid: 000c290c07cf
"""

yaml_content_as_dict = {'play': False,
                        'sound_files': {'dva':
                                            {'current': False,
                                             'file': '2.ogg',
                                             'loaded': True,
                                             'remote': 'url://',
                                             'repeat':
                                                 {'test': 1,
                                                  'retest': 2,
                                                  'hard_list': ['a', 'b', 'c']}
                                             },
                                        'odin':
                                            {'current': False,
                                             'file': '1.ogg',
                                             'loaded': True,
                                             'remote': 'url://',
                                             'repeat': '2'}
                                        },
                        'uid': '000c290c07cf'}